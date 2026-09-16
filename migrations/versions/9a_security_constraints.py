"""Security and integrity constraints

Revision ID: 9a_security_constraints
Revises: 673e0bcd43c2
"""
from alembic import op
import sqlalchemy as sa

revision = "9a_security_constraints"
down_revision = "673e0bcd43c2"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_check_constraint("check_user_role", "role IN ('admin', 'jury', 'artist')")
        batch_op.create_check_constraint("check_account_status", "account_status IN ('ACTIVE', 'INACTIVE')")
        batch_op.create_check_constraint("check_login_attempts", "login_attempts >= 0")
    with op.batch_alter_table("artists") as batch_op:
        batch_op.create_check_constraint("check_competition_status", "competition_status IN ('ACTIVE', 'ELIMINATED')")
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_constraint("unique_assignment", type_="unique")
        batch_op.create_unique_constraint("unique_assignment_per_criterion", ["session_id", "criterion_id"])
    with op.batch_alter_table("criteria") as batch_op:
        batch_op.create_unique_constraint("unique_criterion_name", ["name"])
    with op.batch_alter_table("comments") as batch_op:
        batch_op.create_check_constraint("check_comment_length", "length(comment) <= 500")
        batch_op.create_unique_constraint("unique_comment", ["jury_id", "artist_id", "session_id"])
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.create_check_constraint("check_contact_status", "status IN ('NEW', 'READ', 'REPLIED')")

def downgrade():
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.drop_constraint("check_contact_status", type_="check")
    with op.batch_alter_table("comments") as batch_op:
        batch_op.drop_constraint("unique_comment", type_="unique")
        batch_op.drop_constraint("check_comment_length", type_="check")
    with op.batch_alter_table("criteria") as batch_op:
        batch_op.drop_constraint("unique_criterion_name", type_="unique")
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_constraint("unique_assignment_per_criterion", type_="unique")
        batch_op.create_unique_constraint("unique_assignment", ["session_id", "criterion_id", "evaluator_user_id"])
    with op.batch_alter_table("artists") as batch_op:
        batch_op.drop_constraint("check_competition_status", type_="check")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("check_login_attempts", type_="check")
        batch_op.drop_constraint("check_account_status", type_="check")
        batch_op.drop_constraint("check_user_role", type_="check")
