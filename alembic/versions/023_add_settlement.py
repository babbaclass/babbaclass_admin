"""Add Settlement table and User-Member relationship with birth_date

Revision ID: 023_add_settlement
Revises: 022_drop_partners_table
Create Date: 2025-11-11
"""
from alembic import op
import sqlalchemy as sa


revision = '023_add_settlement'
down_revision = '022_drop_partners_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add birth_date and member_id columns to users table (check if they exist first)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'birth_date' not in columns:
        op.add_column('users', sa.Column('birth_date', sa.String(length=20), nullable=True))
        op.create_index(op.f('ix_users_birth_date'), 'users', ['birth_date'], unique=False)
    
    if 'member_id' not in columns:
        op.add_column('users', sa.Column('member_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_users_member_id'), 'users', ['member_id'], unique=False)
        
        # Create foreign key for member_id
        op.create_foreign_key(
            op.f('fk_users_member_id_members'),
            'users', 'members',
            ['member_id'], ['id']
        )
    
    # Create settlements table if it doesn't exist
    if 'settlements' not in inspector.get_table_names():
        op.create_table(
            'settlements',
            sa.Column('settlement_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('settlement_type', sa.String(length=20), nullable=False),
            sa.Column('settlement_date', sa.DateTime(timezone=True), nullable=False),
            sa.Column('total_commission', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deducted_tax', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deducted_local_tax', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('net_settlement_amount', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('commission_details', sa.Text(), nullable=True),
            sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('paid_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_settlements_user_id_users')),
            sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], name=op.f('fk_settlements_company_id_companies')),
            sa.PrimaryKeyConstraint('settlement_id', name=op.f('pk_settlements'))
        )
        
        # Create indexes on settlements table
        op.create_index(op.f('ix_settlements_user_id'), 'settlements', ['user_id'], unique=False)
        op.create_index(op.f('ix_settlements_company_id'), 'settlements', ['company_id'], unique=False)
        op.create_index(op.f('ix_settlements_settlement_type'), 'settlements', ['settlement_type'], unique=False)
        op.create_index(op.f('ix_settlements_settlement_date'), 'settlements', ['settlement_date'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Drop settlements table if it exists
    if 'settlements' in inspector.get_table_names():
        op.drop_table('settlements')
    
    # Drop foreign key on users.member_id if it exists
    try:
        op.drop_constraint(op.f('fk_users_member_id_members'), 'users', type_='foreignkey')
    except Exception:
        pass
    
    # Drop indexes on users table if they exist
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'member_id' in columns:
        try:
            op.drop_index(op.f('ix_users_member_id'), table_name='users')
        except Exception:
            pass
        op.drop_column('users', 'member_id')
    
    if 'birth_date' in columns:
        try:
            op.drop_index(op.f('ix_users_birth_date'), table_name='users')
        except Exception:
            pass
        op.drop_column('users', 'birth_date')
