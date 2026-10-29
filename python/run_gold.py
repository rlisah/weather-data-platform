
from pathlib import Path

# Reutiliza a conexão RSA que já funciona na Silver
from run_silver import connect_snowflake


def main():
    project_root = Path(__file__).resolve().parents[1]

    sql_files = [
        project_root / "sql/gold/create_weather_metrics.sql",
        project_root / "sql/gold/merge_weather_metrics.sql"
    ]

    conn = connect_snowflake()

    try:
        for sql_file in sql_files:
            sql = sql_file.read_text(encoding="utf-8").strip()

            if not sql:
                raise ValueError(f"Arquivo SQL vazio: {sql_file}")

            print(f"Executando: {sql_file.name}")

            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                conn.commit()
            finally:
                cursor.close()

        print("Transformacao Gold concluida!")

    except Exception:
        conn.rollback()
        print("Erro na transformacao Gold.")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
