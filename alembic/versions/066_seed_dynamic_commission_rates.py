"""Seed dynamic commission rate windows

BASCLE 교재 지사 수수료율 동적 조건 데이터 삽입:
- 기본 25%: 조건 없음
- 27%: 원장 10명 이상 + 월 매출 100만원 이상
- 30%: 원장 20명 이상 + 월 매출 300만원 이상

Revision ID: 066
Revises: 065_dynamic_conditions
Create Date: 2025-12-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '066_seed_dynamic_rates'
down_revision = '065_dynamic_conditions'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # BASCLE commission_type_id 조회
    result = conn.execute(text("SELECT commission_type_id FROM commission_types WHERE code = 'BASCLE' AND is_active = 1 LIMIT 1"))
    row = result.fetchone()
    
    if row:
        bascle_type_id = row[0]
        
        # 기존 BASCLE 관련 rate_windows에서 동적 조건이 없는 기본 레코드가 있는지 확인
        existing = conn.execute(text(f"""
            SELECT id FROM commission_rate_windows 
            WHERE commission_type_id = {bascle_type_id} 
            AND min_teachers IS NULL 
            AND min_monthly_sales IS NULL
            AND start_year = 2025 AND start_month = 11
            LIMIT 1
        """)).fetchone()
        
        if not existing:
            # 2025년 11월부터 적용되는 BASCLE 동적 수수료율 추가
            
            # 1. 기본 25% (조건 없음, 우선순위 낮음)
            conn.execute(text(f"""
                INSERT INTO commission_rate_windows 
                (commission_type_id, start_year, start_month, end_year, end_month, 
                 rate_percent, min_amount, priority, is_active, 
                 min_teachers, min_monthly_sales, role_id, description)
                VALUES 
                ({bascle_type_id}, 2025, 11, NULL, NULL, 
                 25.00, 0, 10, 1, 
                 NULL, NULL, 2, '지사 BASCLE 기본 수수료율')
            """))
            
            # 2. 27% (원장 10명 이상 + 100만원 이상, 우선순위 중간)
            conn.execute(text(f"""
                INSERT INTO commission_rate_windows 
                (commission_type_id, start_year, start_month, end_year, end_month, 
                 rate_percent, min_amount, priority, is_active, 
                 min_teachers, min_monthly_sales, role_id, description)
                VALUES 
                ({bascle_type_id}, 2025, 11, NULL, NULL, 
                 27.00, 0, 20, 1, 
                 10, 1000000, 2, '지사 BASCLE 수수료율 (원장 10명+, 매출 100만원+)')
            """))
            
            # 3. 30% (원장 20명 이상 + 300만원 이상, 우선순위 높음)
            conn.execute(text(f"""
                INSERT INTO commission_rate_windows 
                (commission_type_id, start_year, start_month, end_year, end_month, 
                 rate_percent, min_amount, priority, is_active, 
                 min_teachers, min_monthly_sales, role_id, description)
                VALUES 
                ({bascle_type_id}, 2025, 11, NULL, NULL, 
                 30.00, 0, 30, 1, 
                 20, 3000000, 2, '지사 BASCLE 수수료율 (원장 20명+, 매출 300만원+)')
            """))
            
            print(f"[Seed] Added 3 dynamic BASCLE rate windows for commission_type_id={bascle_type_id}")
        else:
            print("[Seed] Dynamic BASCLE rate windows already exist, skipping")
    else:
        print("[Seed] BASCLE commission type not found, skipping seed")


def downgrade():
    conn = op.get_bind()
    
    # 추가한 동적 조건 레코드만 삭제 (description으로 식별)
    conn.execute(text("""
        DELETE FROM commission_rate_windows 
        WHERE description LIKE '지사 BASCLE%'
        AND start_year = 2025 AND start_month = 11
    """))
