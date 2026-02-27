"""init

Revision ID: a992d4aa995c
Revises: 
Create Date: 2026-02-27 18:22:07.563469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a992d4aa995c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # users — no dependencies
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('providers', postgresql.ARRAY(sa.String()), server_default=sa.text("ARRAY['email']"), nullable=False),
    sa.Column('provider_user_id', sa.String(length=255), nullable=True),
    sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )

    # conversations — create WITHOUT the active_presentation_id FK (circular dep with presentations)
    op.create_table('conversations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('active_presentation_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # presentations — depends on conversations
    op.create_table('presentations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('topic', sa.String(), nullable=False),
    sa.Column('total_pages', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # Now add the deferred FK from conversations → presentations
    op.create_foreign_key(
        'fk_conversations_active_presentation',
        'conversations', 'presentations',
        ['active_presentation_id'], ['id'],
        ondelete='SET NULL'
    )

    # conversation_summaries — depends on conversations
    op.create_table('conversation_summaries',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('summary_content', sa.String(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversation_id', name='uq_conversation_summary_conversation_id')
    )

    # messages — depends on conversations
    op.create_table('messages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('intent', sa.String(), nullable=True),
    sa.Column('is_in_working_memory', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('summarized_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.CheckConstraint("intent IN ('PPTX', 'GENERAL') OR intent IS NULL", name='check_message_intent'),
    sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name='check_message_role'),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # password_reset_tokens — depends on users
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('used_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_expires_at'), 'password_reset_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_token'), 'password_reset_tokens', ['token'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)

    # presentation_pages — depends on presentations
    op.create_table('presentation_pages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('presentation_id', sa.UUID(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('html_content', sa.String(), nullable=False),
    sa.Column('page_title', sa.String(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('presentation_id', 'page_number', name='uq_presentation_page_number')
    )

    # presentation_versions — depends on presentations
    op.create_table('presentation_versions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('presentation_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('total_pages', sa.Integer(), nullable=False),
    sa.Column('user_request', sa.String(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('presentation_id', 'version', name='uq_presentation_version')
    )

    # token_blacklist — depends on users
    op.create_table('token_blacklist',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('token_jti', sa.String(length=255), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_type', sa.String(length=20), nullable=False),
    sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('blacklisted_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_blacklist_expires_at'), 'token_blacklist', ['expires_at'], unique=False)
    op.create_index(op.f('ix_token_blacklist_token_jti'), 'token_blacklist', ['token_jti'], unique=True)
    op.create_index(op.f('ix_token_blacklist_user_id'), 'token_blacklist', ['user_id'], unique=False)

    # user_facts — depends on users
    op.create_table('user_facts',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'key', name='uq_user_fact_key')
    )

    # presentation_version_pages — depends on presentation_versions
    op.create_table('presentation_version_pages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('version_id', sa.UUID(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('html_content', sa.String(), nullable=False),
    sa.Column('page_title', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['version_id'], ['presentation_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id', 'page_number', name='uq_version_page_number')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('presentation_version_pages')
    op.drop_table('user_facts')
    op.drop_index(op.f('ix_token_blacklist_user_id'), table_name='token_blacklist')
    op.drop_index(op.f('ix_token_blacklist_token_jti'), table_name='token_blacklist')
    op.drop_index(op.f('ix_token_blacklist_expires_at'), table_name='token_blacklist')
    op.drop_table('token_blacklist')
    op.drop_table('presentation_versions')
    op.drop_table('presentation_pages')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_token'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_expires_at'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_table('messages')
    op.drop_table('conversation_summaries')
    # Drop deferred FK before dropping conversations
    op.drop_constraint('fk_conversations_active_presentation', 'conversations', type_='foreignkey')
    op.drop_table('presentations')
    op.drop_table('conversations')
    op.drop_table('users')
