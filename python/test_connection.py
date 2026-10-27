import os
import snowflake.connector
from cryptography.hazmat.primitives import serialization


def main():
    private_key = serialization.load_pem_private_key(
        os.environ["SNOWFLAKE_PRIVATE_KEY"].encode("utf-8"),
        password=os.environ[
            "SNOWFLAKE_PRIVATE_KEY_PASSWORD"
        ].encode("utf-8")
    )

    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=private_key_der,
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ["SNOWFLAKE_ROLE"]
    )

    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    CURRENT_USER(),
                    CURRENT_ROLE(),
                    CURRENT_WAREHOUSE()
            """)

            result = cursor.fetchone()

            print("Conexao com Snowflake realizada com sucesso!")
            print("Usuario:", result[0])
            print("Role:", result[1])
            print("Warehouse:", result[2])
        finally:
            cursor.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
