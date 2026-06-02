import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def verify_sync() -> None:
    if not DATABASE_URL:
        print("CRITICAL: DATABASE_URL not found in environment. Check your .env file.")
        return

    print(f"Connecting to: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as conn:
            count_query = text(
                "SELECT COUNT(*) FROM real_estate.properties WHERE source_portal = 'remaxrd'"
            )
            total_records = conn.execute(count_query).scalar()
            print("\n[Database Verification]")
            print(f"-> Total remaxrd records in real_estate.properties: {total_records}")

            sample_query = text(
                """
                SELECT remote_id, title, price_usd, sector, last_modified
                FROM real_estate.properties
                WHERE source_portal = 'remaxrd'
                ORDER BY last_modified DESC
                LIMIT 3
                """
            )
            results = conn.execute(sample_query).fetchall()

            print("\n-> Latest Ingested Samples:")
            for row in results:
                print(
                    f"   - {row.remote_id} | {row.title} | ${row.price_usd} | "
                    f"{row.sector} | modified={row.last_modified}"
                )

    except Exception as e:
        print(f"\n[Database Error] {e}")


if __name__ == "__main__":
    verify_sync()