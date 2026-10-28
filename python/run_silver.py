
import os
import base64
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.primitives import serialization


def connect_snowflake():
    private_key_pem = base64.b64decode(
        os.environ["SNOWFLAKE_PRIVATE_KEY"],
        validate=True
    )

    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=os.environ[
            "SNOWFLAKE_PRIVATE_KEY_PASSWORD"
        ].encode("utf-8")
    )

    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=private_key_der,
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ["SNOWFLAKE_ROLE"],
        database="WEATHER_DATA_PLATFORM",
        autocommit=False
    )


def main():
    sql_path = (
        Path(__file__).resolve().parents[1]
        / "sql"
        / "silver"
        / "merge_weather_daily.sql"
    )

    sql = sql_path.read_text(encoding="utf-8").strip()

    if not sql:
        raise ValueError("O arquivo SQL esta vazio.")

    print("Iniciando transformacao Bronze -> Silver")

    conn = connect_snowflake()

    try:
        cursor = conn.cursor()

        try:
            cursor.execute(sql)
            print("Linhas afetadas:", cursor.rowcount)

            conn.commit()
            print("Transformacao Silver concluida!")

        finally:
            cursor.close()

    except Exception:
        conn.rollback()
        print("Erro na transformacao Silver.")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
