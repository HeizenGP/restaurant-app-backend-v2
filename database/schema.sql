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
-- Integridad adicional en PostgreSQL: los importes históricos son inmutables,
-- las líneas se insertan en la misma transacción que la cabecera, su suma
-- coincide con el total antes de COMMIT y no puede existir sobrepago.
-- ConfirmOrder (autorización, stock + movimiento + comanda en una UoW),
-- cambios de estado, permisos y cierres son casos de uso del backend (ETAPA 08).
-- Los triggers no sustituyen la autorización ni las transacciones de backend.

BEGIN;

-- M01 | Usuarios y accesos ----------------------------------------------
CREATE TABLE public.users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name   VARCHAR(120) NOT NULL,
    email          VARCHAR(254) NOT NULL,
    password_hash  TEXT,
    google_subject VARCHAR(255),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    phone          VARCHAR(30),
    avatar_url     TEXT,
    saved_cards    JSONB NOT NULL DEFAULT '[]'::jsonb,
    saved_addresses JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT ck_users_display_name_not_blank CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_users_email_not_blank CHECK (btrim(email) <> ''),
    CONSTRAINT ck_users_password_hash_not_blank CHECK (
        password_hash IS NULL OR btrim(password_hash) <> ''
    ),
    CONSTRAINT ck_users_has_authentication_method CHECK (
        password_hash IS NOT NULL OR google_subject IS NOT NULL
    ),
    CONSTRAINT uq_users_google_subject UNIQUE (google_subject)
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

CREATE TABLE public.password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    CONSTRAINT ck_password_reset_tokens_expiry CHECK (expires_at > created_at),
    CONSTRAINT uq_password_reset_tokens_token_hash UNIQUE (token_hash)
);
CREATE INDEX ix_password_reset_tokens_user_created
    ON public.password_reset_tokens (user_id, created_at);

CREATE TABLE public.user_addresses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    label           VARCHAR(50) NOT NULL,
    address         VARCHAR(500) NOT NULL,
    department      VARCHAR(50),
    reference       VARCHAR(200),
    delivery_instructions VARCHAR(500),
    recipient_phone VARCHAR(30),
    latitude        NUMERIC(10, 7) NOT NULL,
    longitude       NUMERIC(10, 7) NOT NULL,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_user_addresses_label_not_blank CHECK (btrim(label) <> ''),
    CONSTRAINT ck_user_addresses_address_not_blank CHECK (btrim(address) <> ''),
    CONSTRAINT ck_user_addresses_latitude_range CHECK (latitude >= -90.0 AND latitude <= 90.0),
    CONSTRAINT ck_user_addresses_longitude_range CHECK (longitude >= -180.0 AND longitude <= 180.0)
);
CREATE INDEX ix_user_addresses_user_id ON public.user_addresses (user_id);
CREATE INDEX ix_user_addresses_user_default ON public.user_addresses (user_id, is_default);

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

INSERT INTO public.categories (id, name) VALUES
    ('ca700001-0000-4000-a000-000000000001', 'Arroces y Chaufas'),
    ('ca700001-0000-4000-a000-000000000002', 'Tallarines y Saltados'),
    ('ca700001-0000-4000-a000-000000000003', 'Sopas y Entradas'),
    ('ca700001-0000-4000-a000-000000000004', 'Especialidades'),
    ('ca700001-0000-4000-a000-000000000005', 'Bebidas')
ON CONFLICT (name) DO NOTHING;

INSERT INTO public.products (id, category_id, name, price, stock_qty, is_available)
SELECT
    v.id,
    c.id,
    v.name,
    v.price,
    v.stock_qty,
    v.is_available
FROM (VALUES
    ('b0010001-0000-4000-a000-000000000001'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa Especial', 24.00, 50, TRUE),
    ('b0010001-0000-4000-a000-000000000002'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Pollo', 18.00, 50, TRUE),
    ('b0010001-0000-4000-a000-000000000003'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Carne', 20.00, 50, TRUE),
    ('b0010001-0000-4000-a000-000000000004'::uuid, 'Arroces y Chaufas', 'Aeropuerto Especial', 25.00, 40, TRUE),
    ('b0010001-0000-4000-a000-000000000005'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Chancho', 20.00, 40, TRUE),
    ('b0010002-0000-4000-a000-000000000001'::uuid, 'Tallarines y Saltados', 'Tallarín Saltado de Pollo', 19.00, 45, TRUE),
    ('b0010002-0000-4000-a000-000000000002'::uuid, 'Tallarines y Saltados', 'Tallarín Saltado de Carne', 22.00, 45, TRUE),
    ('b0010002-0000-4000-a000-000000000003'::uuid, 'Tallarines y Saltados', 'Tallarín Taypa Especial', 26.00, 35, TRUE),
    ('b0010002-0000-4000-a000-000000000004'::uuid, 'Tallarines y Saltados', 'Tallarín Sam Si', 24.00, 35, TRUE),
    ('b0010003-0000-4000-a000-000000000001'::uuid, 'Sopas y Entradas', 'Sopa Wantán Especial', 18.00, 30, TRUE),
    ('b0010003-0000-4000-a000-000000000002'::uuid, 'Sopas y Entradas', 'Sopa Fuchifú', 16.00, 30, TRUE),
    ('b0010003-0000-4000-a000-000000000003'::uuid, 'Sopas y Entradas', 'Wantán Frito con Salsa Tamarindo (12 un.)', 14.00, 60, TRUE),
    ('b0010003-0000-4000-a000-000000000004'::uuid, 'Sopas y Entradas', 'Siomay al Vapor (6 un.)', 16.00, 40, TRUE),
    ('b0010004-0000-4000-a000-000000000001'::uuid, 'Especialidades', 'Pollo Chi Jau Kay', 23.00, 40, TRUE),
    ('b0010004-0000-4000-a000-000000000002'::uuid, 'Especialidades', 'Pollo Ti Pa Kay', 23.00, 40, TRUE),
    ('b0010004-0000-4000-a000-000000000003'::uuid, 'Especialidades', 'Kam Lu Wantán', 27.00, 35, TRUE),
    ('b0010004-0000-4000-a000-000000000004'::uuid, 'Especialidades', 'Chancho con Piña', 24.00, 35, TRUE),
    ('b0010005-0000-4000-a000-000000000001'::uuid, 'Bebidas', 'Chicha Morada Clásica (1L)', 10.00, 100, TRUE),
    ('b0010005-0000-4000-a000-000000000002'::uuid, 'Bebidas', 'Inca Kola 500ml', 4.50, 100, TRUE),
    ('b0010005-0000-4000-a000-000000000003'::uuid, 'Bebidas', 'Coca Cola 500ml', 4.50, 100, TRUE),
    ('b0010005-0000-4000-a000-000000000004'::uuid, 'Bebidas', 'Té Jazmín Caliente', 5.00, 80, TRUE)
) AS v(id, category_name, name, price, stock_qty, is_available)
JOIN public.categories c ON c.name = v.category_name
WHERE NOT EXISTS (
    SELECT 1 FROM public.products p WHERE p.id = v.id OR p.name = v.name
);

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

-- El importe de un pedido ya registrado es inmutable.
CREATE FUNCTION public.reject_order_total_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.total_amount IS DISTINCT FROM OLD.total_amount THEN
        RAISE EXCEPTION 'El importe del pedido ya registrado es inmutable'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_orders_total_immutable
    BEFORE UPDATE OF total_amount ON public.orders
    FOR EACH ROW EXECUTE FUNCTION public.reject_order_total_change();

-- El pedido se registra con todas sus líneas en UNA transacción.
-- La comparación de xmin rechaza el alta posterior mientras la cabecera
-- conserve la versión de fila creada junto con sus líneas; es una defensa
-- física acotada, no una garantía independiente del flujo de aplicación.
-- xmin es el XID interno de esta versión de fila y cambia con cada UPDATE.
-- pg_current_xact_id() devuelve xid8; el cast a xid compara el identificador
-- interno de 32 bits sin depender de la API txid_* obsoleta ni de aritmética.
-- CreateOrder debe usar una sola transacción superior: no dividir cabecera y
-- líneas entre nested SAVEPOINT ni actualizar la cabecera antes de insertar
-- todas las líneas. xmin tampoco es una versión de negocio ni debe reutilizarse
-- para control de concurrencia de larga duración.
CREATE FUNCTION public.enforce_order_item_creation_transaction()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_creation_xid xid;
    v_order_status VARCHAR(16);
    v_order_confirmed TIMESTAMPTZ;
BEGIN
    SELECT o.xmin, o.status, o.confirmed_at
      INTO v_creation_xid, v_order_status, v_order_confirmed
      FROM public.orders AS o
     WHERE o.id = NEW.order_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id
            USING ERRCODE = '23503';
    END IF;

    IF v_creation_xid <> pg_current_xact_id()::xid
       OR v_order_status <> 'REQUESTED' OR v_order_confirmed IS NOT NULL THEN
        RAISE EXCEPTION 'Las líneas deben registrarse junto con la cabecera'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_order_items_same_transaction
    BEFORE INSERT ON public.order_items
    FOR EACH ROW EXECUTE FUNCTION public.enforce_order_item_creation_transaction();

-- Bloquea cualquier edición/eliminación de líneas una vez insertadas.
CREATE FUNCTION public.reject_order_item_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'No se permite alterar ni eliminar líneas registradas'
        USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER trg_order_items_immutable
    BEFORE UPDATE OR DELETE ON public.order_items
    FOR EACH ROW EXECUTE FUNCTION public.reject_order_item_change();

-- Constraints diferidos permiten crear cabecera + líneas antes de COMMIT,
-- pero rechazan pedidos sin líneas y totales que no coinciden con su detalle.
CREATE FUNCTION public.check_order_items_total()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_order_id UUID;
    v_total NUMERIC;
    v_lines_total NUMERIC;
BEGIN
    IF TG_TABLE_NAME = 'orders' THEN
        v_order_id := NEW.id;
    ELSE
        v_order_id := NEW.order_id;
    END IF;

    SELECT o.total_amount INTO v_total
      FROM public.orders AS o
     WHERE o.id = v_order_id FOR UPDATE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT COALESCE(SUM(oi.quantity * oi.unit_price_snapshot), 0)
      INTO v_lines_total
      FROM public.order_items AS oi
     WHERE oi.order_id = v_order_id;

    IF v_lines_total <= 0 OR v_total <> v_lines_total THEN
        RAISE EXCEPTION
            'Total del pedido % (%) distinto de sus líneas (%)',
            v_order_id, v_total, v_lines_total
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER ctr_orders_items_total
    AFTER INSERT ON public.orders
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.check_order_items_total();
CREATE CONSTRAINT TRIGGER ctr_order_items_total
    AFTER INSERT ON public.order_items
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.check_order_items_total();

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

-- Auditoría de movimientos: una corrección genera otro movimiento;
-- no se editan ni eliminan registros anteriores.
CREATE FUNCTION public.reject_stock_movement_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Los movimientos de stock históricos son inmutables'
        USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER trg_stock_movements_immutable
    BEFORE UPDATE OR DELETE ON public.stock_movements
    FOR EACH ROW EXECUTE FUNCTION public.reject_stock_movement_change();

-- Compatibilidad de movimiento ORDER con la línea y el pedido confirmado.
-- El descuento de products.stock_qty sigue siendo parte de ConfirmOrder.
CREATE FUNCTION public.check_order_stock_movement()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_product UUID;
    v_quantity INTEGER;
    v_order_status VARCHAR(16);
    v_confirmed_at TIMESTAMPTZ;
BEGIN
    IF NEW.kind <> 'ORDER' THEN
        RETURN NULL;
    END IF;

    SELECT oi.product_id, oi.quantity, o.status, o.confirmed_at
      INTO v_product, v_quantity, v_order_status, v_confirmed_at
      FROM public.order_items AS oi
      JOIN public.orders AS o ON o.id = oi.order_id
     WHERE oi.id = NEW.order_item_id;

    IF NOT FOUND OR NEW.product_id IS DISTINCT FROM v_product
       OR NEW.quantity_delta <> -v_quantity
       OR v_order_status NOT IN ('CONFIRMED', 'CLOSED')
       OR v_confirmed_at IS NULL THEN
        RAISE EXCEPTION 'Movimiento de stock incompatible con pedido confirmado'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER ctr_stock_movement_confirmed
    AFTER INSERT ON public.stock_movements
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.check_order_stock_movement();

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
    ),
    CONSTRAINT ck_kitchen_tickets_state_fields CHECK (
        (status = 'RECEIVED'
            AND started_at IS NULL AND started_by_user_id IS NULL
            AND ready_at IS NULL AND ready_by_user_id IS NULL)
        OR (status = 'PREPARING'
            AND started_at IS NOT NULL AND started_by_user_id IS NOT NULL
            AND ready_at IS NULL AND ready_by_user_id IS NULL)
        OR (status = 'READY'
            AND started_at IS NOT NULL AND started_by_user_id IS NOT NULL
            AND ready_at IS NOT NULL AND ready_by_user_id IS NOT NULL)
    ),
    CONSTRAINT ck_kitchen_tickets_timeline CHECK (
        (started_at IS NULL OR started_at >= created_at)
        AND (ready_at IS NULL OR ready_at >= started_at)
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
-- Bloqueo de cabecera serializa pagos sobre el mismo pedido, garantiza
-- ausencia de saldo negativo y exige anticipo exacto cuando corresponda.
CREATE FUNCTION public.validate_payment_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_total NUMERIC(12,2);
    v_modality VARCHAR(12);
    v_paid NUMERIC;
    v_required NUMERIC;
BEGIN
    SELECT o.total_amount, o.modality INTO v_total, v_modality
      FROM public.orders AS o
     WHERE o.id = NEW.order_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id
            USING ERRCODE = '23503';
    END IF;

    IF NEW.kind = 'ADVANCE' THEN
        IF v_modality NOT IN ('PICKUP', 'DELIVERY') THEN
            RAISE EXCEPTION 'La modalidad LOCAL no admite anticipo'
                USING ERRCODE = '23514';
        END IF;
        v_required := CEIL(v_total * 50) / 100;
        IF NEW.amount <> v_required THEN
            RAISE EXCEPTION 'El anticipo debe ser % y se recibió %',
                v_required, NEW.amount USING ERRCODE = '23514';
        END IF;
    END IF;

    SELECT COALESCE(SUM(p.amount), 0) INTO v_paid
      FROM public.payments AS p
     WHERE p.order_id = NEW.order_id;

    IF v_paid + NEW.amount > v_total THEN
        RAISE EXCEPTION 'El pago supera el saldo pendiente del pedido %',
            NEW.order_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_payments_validate_insert
    BEFORE INSERT ON public.payments
    FOR EACH ROW EXECUTE FUNCTION public.validate_payment_insert();

-- Los importes y demás datos financieros no se alteran ni eliminan.
-- Única excepción: decisión administrativa sobre anticipo, una sola vez.
CREATE FUNCTION public.protect_payment_history()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'No se permite eliminar un pago registrado'
            USING ERRCODE = '23514';
    END IF;

    IF (NEW.id, NEW.order_id, NEW.kind, NEW.amount, NEW.method_code,
        NEW.recorded_by_user_id, NEW.recorded_at, NEW.operation_request_id)
       IS DISTINCT FROM
       (OLD.id, OLD.order_id, OLD.kind, OLD.amount, OLD.method_code,
        OLD.recorded_by_user_id, OLD.recorded_at, OLD.operation_request_id) THEN
        RAISE EXCEPTION 'Los datos financieros del pago son inmutables'
            USING ERRCODE = '23514';
    END IF;

    IF (NEW.refund_decision, NEW.refund_decided_by_user_id, NEW.refund_decided_at)
       IS NOT DISTINCT FROM
       (OLD.refund_decision, OLD.refund_decided_by_user_id, OLD.refund_decided_at) THEN
        RETURN NEW;
    END IF;

    IF OLD.kind <> 'ADVANCE' OR OLD.refund_decision IS NOT NULL
       OR NEW.refund_decision IS NULL OR NEW.refund_decided_by_user_id IS NULL
       OR NEW.refund_decided_at IS NULL THEN
        RAISE EXCEPTION 'La decisión del anticipo solo se registra una vez'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_payments_protect_history
    BEFORE UPDATE OR DELETE ON public.payments
    FOR EACH ROW EXECUTE FUNCTION public.protect_payment_history();

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
-- La autorización de M07, RN-20/RN-21 y requisitos de comprobantes
-- simulados conservan su estado documental. La confirmación exige que
-- M04 valide permisos, stock, anticipo previo y estado, y coordine en
-- UNA transacción: pedido + descuento + movimientos + comanda; ante
-- cualquier error se ejecuta ROLLBACK completo (ETAPA 08).
-- Los controles de stock_qty vs movimientos y las transiciones entre
-- módulos no se resuelven solo con CHECK/trigger: necesitan casos de uso.
-- ETAPA 07: reproducir funciones y triggers en migración Alembic; no
-- aplicar el script directo Y la migración inicial sobre la misma BD.
