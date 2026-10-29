
import os
import json
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import snowflake.connector
from cryptography.hazmat.primitives import serialization


DATABASE = "WEATHER_DATA_PLATFORM"
CITY = "Belo Horizonte"
SOURCE = "OPEN_METEO"

LATITUDE = -19.9167
LONGITUDE = -43.9345

API_URL = "https://api.open-meteo.com/v1/forecast"


def connect_snowflake():
    import base64

    key_pem = base64.b64decode(
        os.environ["SNOWFLAKE_PRIVATE_KEY"],
        validate=True
    )

    private_key = serialization.load_pem_private_key(
        key_pem,
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
        database=DATABASE,
        autocommit=False,
        login_timeout=30,
        session_parameters={
        "TIMEZONE": "UTC"
        }
    )


def extract_weather():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "temperature_2m,relative_humidity_2m",
        "daily": (
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum"
        ),
        "forecast_days": 1,
        "timezone": "America/Sao_Paulo"
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=30
    )
    response.raise_for_status()

    payload = response.json()

    if not payload.get("hourly", {}).get("time"):
        raise ValueError("API retornou dados horarios vazios")

    return payload


def write_manifest(
    cursor,
    batch_id,
    reference_date,
    status,
    bronze_status,
    records_received,
    records_processed,
    started_at,
    error_message=None
):
    cursor.execute(
        """
        INSERT INTO CONTROL.INGESTION_MANIFEST (
            BATCH_ID,
            SOURCE_NAME,
            CITY,
            REFERENCE_DATE,
            STATUS,
            BRONZE_STATUS,
            SILVER_STATUS,
            GOLD_STATUS,
            RECORDS_RECEIVED,
            RECORDS_PROCESSED,
            STARTED_AT,
            FINISHED_AT,
            ERROR_MESSAGE
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            CURRENT_TIMESTAMP(), %s
        )
        """,
        (
            batch_id,
            SOURCE,
            CITY,
            reference_date,
            status,
            bronze_status,
            "PENDING",
            "PENDING",
            records_received,
            records_processed,
            started_at,
            error_message
        )
    )


def main():
    batch_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    reference_date = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).date()

    conn = None
    records_received = 0

    print("Iniciando ingestao")
    print("Batch ID:", batch_id)
    print("Cidade:", CITY)

    try:
        payload = extract_weather()
        records_received = len(payload["hourly"]["time"])

        conn = connect_snowflake()
        cursor = conn.cursor()

        try:
            # Verifica se este identificador ja foi processado.
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM CONTROL.INGESTION_MANIFEST
                WHERE BATCH_ID = %s
                  AND STATUS = 'SUCCESS'
                """,
                (batch_id,)
            )

            if cursor.fetchone()[0] > 0:
                print("Batch ja processado.")
                conn.rollback()
                return

            # Guarda o JSON original como VARIANT.
            cursor.execute(
                """
                INSERT INTO BRONZE.WEATHER_RAW (
                    INGESTION_ID,
                    CITY,
                    SOURCE,
                    PAYLOAD
                )
                SELECT
                    %s,
                    %s,
                    %s,
                    PARSE_JSON(%s)
                """,
                (
                    batch_id,
                    CITY,
                    SOURCE,
                    json.dumps(payload)
                )
            )

            write_manifest(
                cursor=cursor,
                batch_id=batch_id,
                reference_date=reference_date,
                status="SUCCESS",
                bronze_status="SUCCESS",
                records_received=records_received,
                records_processed=1,
                started_at=started_at
            )

            conn.commit()

            print("Ingestao concluida com sucesso!")
            print("Registros horarios recebidos:", records_received)
            print("Payloads gravados na Bronze: 1")

        finally:
            cursor.close()

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        print("Falha na ingestao:", type(exc).__name__)

        # Tenta registrar a falha no Manifest.
        try:
            if conn is None:
                conn = connect_snowflake()

            cursor = conn.cursor()
            try:
                write_manifest(
                    cursor=cursor,
                    batch_id=batch_id,
                    reference_date=reference_date,
                    status="FAILED",
                    bronze_status="FAILED",
                    records_received=records_received,
                    records_processed=0,
                    started_at=started_at,
                    error_message=(
                        type(exc).__name__ + ": " + str(exc)
                    )[:2000]
                )
                conn.commit()
            finally:
                cursor.close()

        except Exception:
            print("Nao foi possivel registrar falha no Manifest.")

        raise

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
