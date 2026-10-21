-- Chifa ASIA | Restaurant App V2
-- Esquema inicial PostgreSQL basado en ETAPA 06 (aprobada 2026-10-21).
-- Contiene 14 tablas (M01-M07 + idempotencia), sus restricciones, índices,
-- los seis roles de referencia y una vista de importes/saldos derivados.
-- DESTINO: solo backend, database/schema.sql. No es una migración Alembic.
-- PostgreSQL 13+ (gen_random_uuid() incorporado en PostgreSQL).
-- Requiere una base de datos VACÍA y existente; no crea ni elimina bases.
-- Ejemplo de ejecución MANUAL (NO realizada):
--   psql -X -v ON_ERROR_STOP=1 -d NOMBRE_BD -f database/schema.sql
-- No ejecutar de nuevo sobre una BD ya migrada por Alembic.
-- Permisos, transiciones entre tablas, total de líneas, anticipo confirmado,
-- saldos no negativos, consistencia de stock y confirmación atómica son
-- invariantes a implementar en los casos de uso transaccionales (ETAPA 08).

BEGIN;

-- M01 | Usuarios y accesos ----------------------------------------------
CREATE TABLE public.users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name   VARCHAR(120) NOT NULL,
    email          VARCHAR(254) NOT NULL,
    password_hash  TEXT NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_users_display_name_not_blank CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_users_email_not_blank CHECK (btrim(email) <> ''),
    CONSTRAINT ck_users_password_hash_not_blank CHECK (btrim(password_hash) <> '')
);
CREATE UNIQUE INDEX ux_users_email_ci ON public.users (lower(email));

CREATE TABLE public.roles (
    code  VARCHAR(32) PRIMARY KEY,
    label VARCHAR(80) NOT NULL,
    CONSTRAINT ck_roles_code CHECK (
        code IN ('CUSTOMER', 'WAITER', 'CASHIER', 'ADMIN', 'KITCHEN', 'SUPER_ADMIN')
    ),
    CONSTRAINT ck_roles_label_not_blank CHECK (btrim(label) <> '')
);

-- Valores de referencia de los seis actores; GUEST es una sesión, no un rol.
INSERT INTO public.roles (code, label) VALUES
    ('CUSTOMER',    'Cliente'),
    ('WAITER',      'Mozo'),
    ('CASHIER',     'Cajero'),
    ('ADMIN',       'Administrador'),
    ('KITCHEN',     'Personal de cocina'),
    ('SUPER_ADMIN', 'Superadministrador');

CREATE TABLE public.user_roles (
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    role_code  VARCHAR(32) NOT NULL REFERENCES public.roles(code) ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_code)
);
CREATE INDEX ix_user_roles_role_code_user_id ON public.user_roles (role_code, user_id);

CREATE TABLE public.auth_sessions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                 VARCHAR(12) NOT NULL,
    user_id              UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    renewal_token_hash   TEXT UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at           TIMESTAMPTZ NOT NULL,
    revoked_at           TIMESTAMPTZ,
    CONSTRAINT ck_sessions_kind CHECK (kind IN ('USER', 'GUEST')),
    CONSTRAINT ck_sessions_kind_user CHECK (
        (kind = 'USER' AND user_id IS NOT NULL)
        OR (kind = 'GUEST' AND user_id IS NULL)
    ),
    CONSTRAINT ck_sessions_expiry CHECK (expires_at > created_at)
);
CREATE INDEX ix_sessions_user_expiry ON public.auth_sessions (user_id, expires_at);

-- M02 | Catálogo, producto terminado y movimientos ---------------------
CREATE TABLE public.categories (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    CONSTRAINT ck_categories_name_not_blank CHECK (btrim(name) <> '')
);

CREATE TABLE public.products (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id  UUID NOT NULL REFERENCES public.categories(id) ON DELETE RESTRICT,
    name         VARCHAR(160) NOT NULL,
    price        NUMERIC(12,2) NOT NULL,
    stock_qty    INTEGER NOT NULL DEFAULT 0,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_products_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0),
    CONSTRAINT ck_products_stock_nonnegative CHECK (stock_qty >= 0)
);
CREATE INDEX ix_products_category_available ON public.products (category_id, is_available);

-- M03 | Mesas (único restaurante) --------------------------------------
CREATE TABLE public.restaurant_tables (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code               VARCHAR(24) NOT NULL UNIQUE,
    area_label         VARCHAR(80),
    is_occupied        BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by_user_id UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_restaurant_tables_code_not_blank CHECK (btrim(code) <> '')
);

-- M04 | Pedidos ---------------------------------------------------------
CREATE TABLE public.orders (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    modality              VARCHAR(12) NOT NULL,
    channel               VARCHAR(12) NOT NULL,
    status                VARCHAR(16) NOT NULL DEFAULT 'REQUESTED',
    customer_user_id      UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    guest_session_id      UUID REFERENCES public.auth_sessions(id) ON DELETE RESTRICT,
    created_by_user_id    UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    table_id              UUID REFERENCES public.restaurant_tables(id) ON DELETE RESTRICT,
    delivery_address      TEXT,
    contact_name          VARCHAR(120),
    contact_phone         VARCHAR(30),
    total_amount          NUMERIC(12,2) NOT NULL,
    version               INTEGER NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by_user_id    UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    decided_at            TIMESTAMPTZ,
    table_verified_at     TIMESTAMPTZ,
    confirmed_by_user_id  UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    confirmed_at          TIMESTAMPTZ,
    closed_by_user_id     UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    closed_at             TIMESTAMPTZ,
    CONSTRAINT ck_orders_modality CHECK (modality IN ('LOCAL', 'PICKUP', 'DELIVERY')),
    CONSTRAINT ck_orders_channel CHECK (channel IN ('APP', 'WAITER', 'PHONE', 'WHATSAPP')),
    CONSTRAINT ck_orders_status CHECK (
        status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CONFIRMED', 'CANCELLED', 'CLOSED')
    ),
    CONSTRAINT ck_orders_total_positive CHECK (total_amount > 0),
    CONSTRAINT ck_orders_version_nonnegative CHECK (version >= 0),
    CONSTRAINT ck_orders_modality_fields CHECK (
        (modality = 'LOCAL' AND table_id IS NOT NULL AND delivery_address IS NULL)
        OR (modality = 'PICKUP' AND table_id IS NULL AND delivery_address IS NULL)
        OR (modality = 'DELIVERY' AND table_id IS NULL
            AND NULLIF(btrim(delivery_address), '') IS NOT NULL)
    ),
    CONSTRAINT ck_orders_channel_modality CHECK (
        (channel = 'WAITER' AND modality = 'LOCAL')
        OR (channel IN ('PHONE','WHATSAPP') AND modality IN ('PICKUP','DELIVERY'))
        OR (channel = 'APP')
    ),
    CONSTRAINT ck_orders_requester CHECK (
        (channel = 'APP' AND num_nonnulls(customer_user_id, guest_session_id) = 1)
        OR (channel <> 'APP' AND created_by_user_id IS NOT NULL)
    ),
    CONSTRAINT ck_orders_decision_pair CHECK (
        (decided_by_user_id IS NULL) = (decided_at IS NULL)
    ),
    CONSTRAINT ck_orders_confirmed_pair CHECK (
        (confirmed_by_user_id IS NULL) = (confirmed_at IS NULL)
    ),
    CONSTRAINT ck_orders_closed_pair CHECK (
        (closed_by_user_id IS NULL) = (closed_at IS NULL)
    )
);
CREATE INDEX ix_orders_customer_created ON public.orders (customer_user_id, created_at DESC)
    WHERE customer_user_id IS NOT NULL;
CREATE INDEX ix_orders_guest_created ON public.orders (guest_session_id, created_at DESC)
    WHERE guest_session_id IS NOT NULL;
CREATE INDEX ix_orders_status_created ON public.orders (status, created_at DESC);
CREATE INDEX ix_orders_table_id ON public.orders (table_id)
    WHERE table_id IS NOT NULL;

CREATE TABLE public.order_items (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id              UUID NOT NULL REFERENCES public.orders(id) ON DELETE RESTRICT,
    product_id            UUID NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    product_name_snapshot VARCHAR(160) NOT NULL,
    quantity              INTEGER NOT NULL,
    unit_price_snapshot   NUMERIC(12,2) NOT NULL,
    CONSTRAINT uq_order_items_order_product UNIQUE (order_id, product_id),
    CONSTRAINT ck_order_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_order_items_price_nonnegative CHECK (unit_price_snapshot >= 0),
    CONSTRAINT ck_order_items_name_not_blank CHECK (btrim(product_name_snapshot) <> '')
);
CREATE INDEX ix_order_items_product ON public.order_items (product_id);

-- M02 (continuación) | Los movimientos refieren a líneas de pedido -----
CREATE TABLE public.stock_movements (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id     UUID NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    kind           VARCHAR(12) NOT NULL,
    quantity_delta INTEGER NOT NULL,
    order_item_id  UUID REFERENCES public.order_items(id) ON DELETE RESTRICT,
    actor_user_id  UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_stock_movements_kind CHECK (kind IN ('MANUAL', 'ORDER')),
    CONSTRAINT ck_stock_movements_shape CHECK (
        (kind = 'MANUAL' AND order_item_id IS NULL AND quantity_delta <> 0)
        OR (kind = 'ORDER' AND order_item_id IS NOT NULL AND quantity_delta < 0)
    )
);
CREATE UNIQUE INDEX ux_stock_movements_order_item ON public.stock_movements (order_item_id)
    WHERE kind = 'ORDER';
CREATE INDEX ix_stock_movements_product_recorded
    ON public.stock_movements (product_id, recorded_at DESC);

-- M05 | Cocina ---------------------------------------------------------
CREATE TABLE public.kitchen_tickets (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           UUID NOT NULL UNIQUE REFERENCES public.orders(id) ON DELETE RESTRICT,
    status             VARCHAR(20) NOT NULL DEFAULT 'RECEIVED',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at         TIMESTAMPTZ,
    ready_at           TIMESTAMPTZ,
    started_by_user_id UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    ready_by_user_id   UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_kitchen_tickets_status CHECK (status IN ('RECEIVED','PREPARING','READY')),
    CONSTRAINT ck_kitchen_tickets_started_pair CHECK (
        (started_at IS NULL) = (started_by_user_id IS NULL)
    ),
    CONSTRAINT ck_kitchen_tickets_ready_pair CHECK (
        (ready_at IS NULL) = (ready_by_user_id IS NULL)
    )
);
CREATE INDEX ix_kitchen_tickets_status_created
    ON public.kitchen_tickets (status, created_at);

-- Soporte transversal: idempotencia sin duplicar acciones ----------------
CREATE TABLE public.idempotency_requests (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id          UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    actor_guest_session_id UUID REFERENCES public.auth_sessions(id) ON DELETE RESTRICT,
    operation              VARCHAR(40) NOT NULL,
    request_key            VARCHAR(128) NOT NULL,
    request_hash           CHAR(64) NOT NULL,
    result_order_id        UUID REFERENCES public.orders(id) ON DELETE RESTRICT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at             TIMESTAMPTZ NOT NULL,
    completed_at           TIMESTAMPTZ,
    CONSTRAINT ck_idempotency_actor CHECK (
        num_nonnulls(actor_user_id, actor_guest_session_id) = 1
    ),
    CONSTRAINT ck_idempotency_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_idempotency_operation_not_blank CHECK (btrim(operation) <> ''),
    CONSTRAINT ck_idempotency_key_not_blank CHECK (btrim(request_key) <> ''),
    CONSTRAINT ck_idempotency_hash_hex CHECK (request_hash ~ '^[0-9a-fA-F]{64}$')
);
CREATE UNIQUE INDEX ux_idempotency_user_request
    ON public.idempotency_requests (actor_user_id, operation, request_key)
    WHERE actor_user_id IS NOT NULL;
CREATE UNIQUE INDEX ux_idempotency_guest_request
    ON public.idempotency_requests (actor_guest_session_id, operation, request_key)
    WHERE actor_guest_session_id IS NOT NULL;
CREATE INDEX ix_idempotency_expiry ON public.idempotency_requests (expires_at);

-- M06 | Pagos simulados y anticipos ------------------------------------
CREATE TABLE public.payments (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id                  UUID NOT NULL REFERENCES public.orders(id) ON DELETE RESTRICT,
    kind                      VARCHAR(12) NOT NULL,
    amount                    NUMERIC(12,2) NOT NULL,
    method_code               VARCHAR(24),
    recorded_by_user_id       UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    recorded_at               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation_request_id      UUID NOT NULL UNIQUE
                              REFERENCES public.idempotency_requests(id) ON DELETE RESTRICT,
    refund_decision           VARCHAR(12),
    refund_decided_by_user_id UUID REFERENCES public.users(id) ON DELETE RESTRICT,
    refund_decided_at         TIMESTAMPTZ,
    CONSTRAINT ck_payments_kind CHECK (kind IN ('ADVANCE','COLLECTION')),
    CONSTRAINT ck_payments_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_payments_refund_decision CHECK (
        refund_decision IS NULL OR refund_decision IN ('APPROVED','DENIED')
    ),
    CONSTRAINT ck_payments_refund_fields CHECK (
        (refund_decision IS NULL AND refund_decided_by_user_id IS NULL AND refund_decided_at IS NULL)
        OR (kind = 'ADVANCE' AND refund_decision IS NOT NULL
            AND refund_decided_by_user_id IS NOT NULL AND refund_decided_at IS NOT NULL)
    )
);
CREATE UNIQUE INDEX ux_payments_one_advance_per_order ON public.payments (order_id)
    WHERE kind = 'ADVANCE';
CREATE INDEX ix_payments_order_recorded ON public.payments (order_id, recorded_at);

-- M07 | Servicio, recojo o entrega comercial ----------------------------
CREATE TABLE public.fulfillments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL UNIQUE REFERENCES public.orders(id) ON DELETE RESTRICT,
    kind                VARCHAR(16) NOT NULL,
    recorded_by_user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_fulfillments_kind CHECK (kind IN ('SERVED','PICKED_UP','DELIVERED'))
);

-- Consulta derivada: no añadir columnas redundantes de saldo.
-- Para PICKUP/DELIVERY: anticipo = CEIL(total * 50)/100 (céntimo superior).
-- Ej.: 10.01 -> anticipo 5.01 y restante inicial 5.00.
-- El saldo actual siempre descuenta exclusivamente pagos SIMULADOS ya registrados;
-- una decisión de devolución no significa un reembolso ejecutado.
CREATE VIEW public.order_payment_summary AS
SELECT
    o.id AS order_id,
    o.modality,
    o.total_amount,
    CASE WHEN o.modality IN ('PICKUP','DELIVERY')
        THEN (CEIL(o.total_amount * 50) / 100)::NUMERIC(12,2)
        ELSE 0::NUMERIC(12,2)
    END AS required_advance,
    CASE WHEN o.modality IN ('PICKUP','DELIVERY')
        THEN (o.total_amount - CEIL(o.total_amount * 50) / 100)::NUMERIC(12,2)
        ELSE o.total_amount
    END AS remaining_after_required_advance,
    COALESCE(SUM(p.amount) FILTER (WHERE p.kind = 'ADVANCE'), 0)::NUMERIC(12,2)
        AS recorded_advance,
    COALESCE(SUM(p.amount), 0)::NUMERIC(12,2) AS paid_total,
    (o.total_amount - COALESCE(SUM(p.amount), 0))::NUMERIC(12,2)
        AS balance_due
FROM public.orders o
LEFT JOIN public.payments p ON p.order_id = o.id
GROUP BY o.id, o.modality, o.total_amount;

COMMIT;

-- NOTA PARA ETAPA 07/08:
-- Esta definición se utilizará como referencia para los modelos SQLAlchemy Async
-- y migraciones Alembic; evitar aplicarla junto con una migración inicial equivalente.
-- La autorización de M07, las reglas RN-20/RN-21 y el alcance específico de emisión
-- de comprobantes simulados permanecen según su estado documental.