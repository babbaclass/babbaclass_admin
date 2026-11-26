"""fix empty json objects to arrays in commission types

Revision ID: 047
Revises: 046
Create Date: 2025-11-26

기존 commission_types 테이블의 cate1_code_list, cate1_name_list 필드에서
빈 객체 {}를 빈 배열 []로 일괄 수정
"""
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '047'
down_revision = '046'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    commission_types 테이블의 JSON 필드에서 빈 객체 {}를 빈 배열 []로 변경
    """
    # MySQL의 JSON 함수를 사용하여 {} -> [] 변환
    connection = op.get_bind()
    
    # cate1_code_list 필드 업데이트
    connection.execute(
        text("""
            UPDATE commission_types 
            SET cate1_code_list = JSON_ARRAY()
            WHERE cate1_code_list IS NOT NULL 
            AND JSON_TYPE(cate1_code_list) = 'OBJECT'
            AND JSON_LENGTH(cate1_code_list) = 0
        """)
    )
    
    # cate1_name_list 필드 업데이트
    connection.execute(
        text("""
            UPDATE commission_types 
            SET cate1_name_list = JSON_ARRAY()
            WHERE cate1_name_list IS NOT NULL 
            AND JSON_TYPE(cate1_name_list) = 'OBJECT'
            AND JSON_LENGTH(cate1_name_list) = 0
        """)
    )


def downgrade() -> None:
    """
    롤백: 빈 배열 []를 빈 객체 {}로 되돌림
    """
    connection = op.get_bind()
    
    # cate1_code_list 필드 롤백
    connection.execute(
        text("""
            UPDATE commission_types 
            SET cate1_code_list = JSON_OBJECT()
            WHERE cate1_code_list IS NOT NULL 
            AND JSON_TYPE(cate1_code_list) = 'ARRAY'
            AND JSON_LENGTH(cate1_code_list) = 0
        """)
    )
    
    # cate1_name_list 필드 롤백
    connection.execute(
        text("""
            UPDATE commission_types 
            SET cate1_name_list = JSON_OBJECT()
            WHERE cate1_name_list IS NOT NULL 
            AND JSON_TYPE(cate1_name_list) = 'ARRAY'
            AND JSON_LENGTH(cate1_name_list) = 0
        """)
    )
