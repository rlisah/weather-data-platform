import os
import base64
import snowflake.connector
from cryptography.hazmat.primitives import serialization


def main():

    # 1. Recuperar chave RSA do GitHub Secrets
    private_key_base64 = os.environ["SNOWFLAKE_PRIVATE_KEY"]

    # 2. Converter Base64 para o arquivo PEM original
    private_key_pem = base64.b64decode(
        private_key_base64,
        validate=True
    )

    # 3. Descriptografar a chave com a senha
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=os.environ[
            "SNOWFLAKE_PRIVATE_KEY_PASSWORD"
        ].encode("utf-8")
    )

    # 4. Converter para DER (formato aceito pelo conector)
    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # 5. Conectar ao Snowflake
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=private_key_der,
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ["SNOWFLAKE_ROLE"],
        login_timeout=30
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
