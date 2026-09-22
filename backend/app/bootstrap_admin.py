import typer
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlmodel import Session

from app import crud
from app.core.db import engine
from app.models import UserCreate, UserRole
from app.services.audit import record_audit

cli = typer.Typer(help="Protected one-time administrator bootstrap.")


@cli.command()
def create(email: str, full_name: str | None = None) -> None:
    try:
        validated_email = TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        raise typer.BadParameter("A valid email address is required") from None
    with Session(engine) as session:
        if crud.get_user_by_email(session=session, email=validated_email):
            raise typer.BadParameter("A user with this email already exists")
        user, password = crud.create_user(
            session=session,
            user_create=UserCreate(
                email=validated_email, full_name=full_name, role=UserRole.ADMIN
            ),
        )
        record_audit(
            session,
            actor_id=user.id,
            action="administrator.bootstrapped",
            resource_type="user",
            resource_id=user.id,
        )
        session.commit()
    typer.echo(f"Administrator created: {validated_email}")
    typer.echo(f"One-time temporary password: {password}")
    typer.echo(
        "Store it securely. It will not be shown again and must be changed at sign-in."
    )


if __name__ == "__main__":
    cli()
