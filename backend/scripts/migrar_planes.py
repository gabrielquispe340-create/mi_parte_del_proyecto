"""Migración aditiva e idempotente: planes del SaaS para universidades.

- saas_plan: catálogo de planes (columna audience lista para planes de empresa a futuro).
- educational_institution.plan_code / plan_paid_until: plan de cada universidad cliente y
  hasta cuándo está pagado.
- university_signup_request: solicitudes de alta que envían las universidades desde la
  página pública; el superadmin las aprueba o rechaza.
- plan_payment: pagos anuales de cada universidad, con tarjeta (Stripe Checkout) o manuales
  (los registra el superadmin, p. ej. por transferencia).

Las universidades sin plan se tratan como Básico, así que el código que no conoce estas
columnas sigue funcionando.

Uso (desde la carpeta backend):
    python -m scripts.migrar_planes
"""

from sqlalchemy import text

from app.core.database import engine

DDL = [
    """CREATE TABLE IF NOT EXISTS saas_plan (
        code varchar(30) PRIMARY KEY,
        audience varchar(20) NOT NULL DEFAULT 'university',
        name varchar(60) NOT NULL,
        price_bs_year numeric(10, 2) NOT NULL DEFAULT 0,
        max_graduates integer,
        max_moderators integer,
        employability_reports boolean NOT NULL DEFAULT false,
        custom_branding boolean NOT NULL DEFAULT false,
        sort_order smallint NOT NULL DEFAULT 0,
        CONSTRAINT ck_saas_plan_audience CHECK (audience IN ('university', 'company'))
    )""",
    "ALTER TABLE saas_plan ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE educational_institution ADD COLUMN IF NOT EXISTS plan_code varchar(30) REFERENCES saas_plan(code)",
    "ALTER TABLE educational_institution ADD COLUMN IF NOT EXISTS plan_paid_until date",
    """CREATE TABLE IF NOT EXISTS university_signup_request (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        institution_id uuid REFERENCES educational_institution(id) ON DELETE SET NULL,
        name varchar(200) NOT NULL,
        acronym varchar(20) NOT NULL,
        city varchar(100),
        contact_name varchar(150) NOT NULL,
        contact_email varchar(255) NOT NULL,
        contact_phone varchar(40),
        plan_code varchar(30) NOT NULL REFERENCES saas_plan(code),
        status varchar(20) NOT NULL DEFAULT 'pending',
        rejection_reason text,
        created_at timestamptz NOT NULL DEFAULT now(),
        reviewed_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
        reviewed_at timestamptz,
        CONSTRAINT ck_univ_signup_status CHECK (status IN ('pending', 'approved', 'rejected'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_univ_signup_status ON university_signup_request (status, created_at)",
    "ALTER TABLE university_signup_request ENABLE ROW LEVEL SECURITY",
    """CREATE TABLE IF NOT EXISTS plan_payment (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        institution_id uuid NOT NULL REFERENCES educational_institution(id) ON DELETE CASCADE,
        plan_code varchar(30) NOT NULL REFERENCES saas_plan(code),
        amount_bs numeric(10, 2) NOT NULL,
        method varchar(20) NOT NULL,
        status varchar(20) NOT NULL DEFAULT 'pending',
        stripe_session_id varchar(255) UNIQUE,
        paid_until date,
        created_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        paid_at timestamptz,
        CONSTRAINT ck_plan_payment_method CHECK (method IN ('stripe', 'manual')),
        CONSTRAINT ck_plan_payment_status CHECK (status IN ('pending', 'paid', 'expired'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_plan_payment_institution ON plan_payment (institution_id, created_at)",
    "ALTER TABLE plan_payment ENABLE ROW LEVEL SECURITY",
]

# NULL en los límites = sin límite. Precios anuales en bolivianos.
PLANES = [
    ("basico", "Básico", 0, 300, 1, False, False, 1),
    ("profesional", "Profesional", 4800, 3000, 5, True, False, 2),
    ("institucional", "Institucional", 12000, None, None, True, True, 3),
]

# Plan inicial de las universidades cliente de la demo (solo si todavía no tienen uno).
# Unifranz queda con el pago pendiente para mostrar ese estado.
PLANES_INICIALES = {
    "50000000-0000-0000-0000-000000000001": ("institucional", True),  # UAGRM
    "50000000-0000-0000-0000-000000000002": ("profesional", True),  # UMSS
    "50000000-0000-0000-0000-000000000003": ("basico", False),  # UMSA
    "50000000-0000-0000-0000-000000000005": ("profesional", False),  # Unifranz
}


def ejecutar() -> None:
    with engine.begin() as conn:
        print("[1/3] Aplicando cambios de esquema (aditivos)...")
        for sentencia in DDL:
            conn.execute(text(sentencia))

        print("[2/3] Cargando el catálogo de planes...")
        for code, name, precio, max_egr, max_mod, reportes, marca, orden in PLANES:
            conn.execute(
                text(
                    """INSERT INTO saas_plan (code, audience, name, price_bs_year, max_graduates, max_moderators,
                                              employability_reports, custom_branding, sort_order)
                       VALUES (:code, 'university', :name, :precio, :max_egr, :max_mod, :reportes, :marca, :orden)
                       ON CONFLICT (code) DO UPDATE SET
                           name = EXCLUDED.name, price_bs_year = EXCLUDED.price_bs_year,
                           max_graduates = EXCLUDED.max_graduates, max_moderators = EXCLUDED.max_moderators,
                           employability_reports = EXCLUDED.employability_reports,
                           custom_branding = EXCLUDED.custom_branding, sort_order = EXCLUDED.sort_order"""
                ),
                {"code": code, "name": name, "precio": precio, "max_egr": max_egr, "max_mod": max_mod,
                 "reportes": reportes, "marca": marca, "orden": orden},
            )

        print("[3/3] Asignando plan a las universidades cliente sin plan...")
        for inst_id, (plan, pagado) in PLANES_INICIALES.items():
            r = conn.execute(
                text(
                    """UPDATE educational_institution
                       SET plan_code = :plan,
                           plan_paid_until = CASE WHEN :pagado THEN (now() + interval '1 year')::date END
                       WHERE id = :id AND plan_code IS NULL"""
                ),
                {"plan": plan, "pagado": pagado, "id": inst_id},
            )
            print(f"  {inst_id} -> {plan}{' (pagado)' if pagado else ''}: {r.rowcount}")

    print("Listo: planes del SaaS disponibles.")


if __name__ == "__main__":
    ejecutar()
