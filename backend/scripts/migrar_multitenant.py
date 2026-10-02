"""Migración aditiva e idempotente para el modelo multitenant (SaaS multi-universidad).

Tenant = universidad (tabla existente educational_institution). Las empresas son
globales y se vinculan a una o varias universidades mediante company_institution.

Solo agrega columnas opcionales, una tabla nueva e índices, y asigna los datos
existentes a la UAGRM: el código que no conoce estas columnas sigue funcionando.

Uso (desde la carpeta backend):
    python -m scripts.migrar_multitenant
"""

from sqlalchemy import text

from app.core.database import engine
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID

UNIVERSIDADES_CLIENTE = {
    "50000000-0000-0000-0000-000000000001": "uagrm",
    "50000000-0000-0000-0000-000000000002": "umss",
    "50000000-0000-0000-0000-000000000003": "umsa",
    "50000000-0000-0000-0000-000000000005": "unifranz",
}

STAFF_UAGRM = ("admin@uagrm.bo", "admin2@uagrm.bo", "moderador@uagrm.bo")

DDL = [
    "ALTER TABLE educational_institution ADD COLUMN IF NOT EXISTS slug varchar(40)",
    "ALTER TABLE educational_institution ADD COLUMN IF NOT EXISTS is_tenant boolean NOT NULL DEFAULT false",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_edu_inst_slug ON educational_institution (slug) WHERE slug IS NOT NULL",
    """ALTER TABLE candidate_profile ADD COLUMN IF NOT EXISTS institution_id uuid
       REFERENCES educational_institution(id) ON DELETE SET NULL""",
    "CREATE INDEX IF NOT EXISTS ix_cand_profile_institution ON candidate_profile (institution_id)",
    """ALTER TABLE app_user ADD COLUMN IF NOT EXISTS institution_id uuid
       REFERENCES educational_institution(id) ON DELETE SET NULL""",
    """CREATE TABLE IF NOT EXISTS company_institution (
        company_id uuid NOT NULL REFERENCES company(id) ON DELETE CASCADE,
        institution_id uuid NOT NULL REFERENCES educational_institution(id) ON DELETE CASCADE,
        status varchar(20) NOT NULL DEFAULT 'pending',
        rejection_reason text,
        requested_at timestamptz NOT NULL DEFAULT now(),
        reviewed_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
        reviewed_at timestamptz,
        PRIMARY KEY (company_id, institution_id),
        CONSTRAINT ck_comp_inst_status CHECK (status IN ('pending', 'approved', 'rejected', 'suspended'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_company_institution_inst ON company_institution (institution_id, status)",
    # Mismo criterio que el resto de tablas del esquema: RLS activo, el backend accede como dueño.
    "ALTER TABLE company_institution ENABLE ROW LEVEL SECURITY",
]


def ejecutar() -> None:
    with engine.begin() as conn:
        print("[1/4] Aplicando cambios de esquema (aditivos)...")
        for sentencia in DDL:
            conn.execute(text(sentencia))

        print("[2/4] Marcando universidades cliente del SaaS...")
        for inst_id, slug in UNIVERSIDADES_CLIENTE.items():
            conn.execute(
                text("UPDATE educational_institution SET slug = :slug, is_tenant = true WHERE id = :id"),
                {"slug": slug, "id": inst_id},
            )

        print("[3/4] Asignando datos existentes a la UAGRM...")
        r = conn.execute(
            text("UPDATE candidate_profile SET institution_id = :inst WHERE institution_id IS NULL"),
            {"inst": str(INSTITUCION_POR_DEFECTO_ID)},
        )
        print(f"  egresados asignados: {r.rowcount}")
        r = conn.execute(
            text("UPDATE app_user SET institution_id = :inst WHERE email = ANY(:correos) AND institution_id IS NULL"),
            {"inst": str(INSTITUCION_POR_DEFECTO_ID), "correos": list(STAFF_UAGRM)},
        )
        print(f"  staff UAGRM asignado: {r.rowcount}")

        print("[4/4] Vinculando empresas existentes a la UAGRM...")
        r = conn.execute(
            text(
                """INSERT INTO company_institution (company_id, institution_id, status, reviewed_at)
                   SELECT id, :inst,
                          CASE WHEN account_status = 'suspended' THEN 'suspended'
                               WHEN verification_status = 'verified' THEN 'approved'
                               WHEN verification_status = 'rejected' THEN 'rejected'
                               ELSE 'pending' END,
                          CASE WHEN verification_status IN ('verified', 'rejected') THEN now() END
                   FROM company
                   ON CONFLICT (company_id, institution_id) DO NOTHING"""
            ),
            {"inst": str(INSTITUCION_POR_DEFECTO_ID)},
        )
        print(f"  vínculos creados: {r.rowcount}")

    print("Listo: migración multitenant aplicada.")


if __name__ == "__main__":
    ejecutar()
