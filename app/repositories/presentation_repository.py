"""
Presentation repository - Data access layer for presentations.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import (
    Presentation,
    PresentationPage,
    PresentationVersion,
    PresentationVersionPage,
    Conversation
)
from app.types.llm.outputs import PageContent
from app.types.internal.presentation import (
    Presentation as PresentationDict,
    PresentationWithPages,
    PresentationVersion as PresentationVersionDict,
    VersionContent,
)
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class PresentationRepository:

    def __init__(self, db: Session):
        self.db = db

    def create_presentation(
        self,
        presentation: PresentationDict,
        pages: List[PageContent],
        user_request: str,
        user_id: str,
    ) -> Optional[PresentationDict]:
        """
        Create new presentation in database.

        Args:
            presentation: Presentation dict with conversation_id, topic, total_pages
            pages: List of PageContent objects
            user_request: User's request text
            user_id: UUID of the user (for ownership check)

        Returns:
            Presentation dict with id and created_at set if successful, None otherwise
        """
        try:
            # Verify conversation belongs to user
            conversation = self.db.query(Conversation).filter(
                Conversation.id == presentation["conversation_id"],
                Conversation.user_id == user_id
            ).first()

            if not conversation:
                return None

            new_presentation = Presentation(
                conversation_id=presentation["conversation_id"],
                topic=presentation["topic"],
                total_pages=presentation["total_pages"],
                version=presentation.get("version", 1),
                pres_metadata={"user_request": user_request}
            )

            self.db.add(new_presentation)
            self.db.flush()

            for page in pages:
                new_page = PresentationPage(
                    presentation_id=new_presentation.id,
                    page_number=page.page_number,
                    html_content=page.html_content,
                    page_title=page.page_title
                )
                self.db.add(new_page)

            # Set as active presentation
            conversation.active_presentation_id = new_presentation.id

            self.db.commit()
            self.db.refresh(new_presentation)

            return {
                "id": str(new_presentation.id),
                "conversation_id": str(new_presentation.conversation_id),
                "topic": new_presentation.topic,
                "total_pages": new_presentation.total_pages,
                "version": new_presentation.version,
                "metadata": new_presentation.pres_metadata,
                "created_at": new_presentation.created_at.isoformat() if new_presentation.created_at else None,
                "updated_at": new_presentation.updated_at.isoformat() if new_presentation.updated_at else None,
            }

        except Exception as e:
            logger.exception("create_presentation_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to create presentation: {e}") from e

    def load_presentation(self, presentation_id: str, user_id: str) -> Optional[PresentationWithPages]:
        """
        Load presentation with current version pages.

        Args:
            presentation_id: UUID of presentation
            user_id: UUID of the user (for ownership check)

        Returns:
            PresentationWithPages dict with pages included, or None
        """
        try:
            presentation = (
                self.db.query(Presentation)
                .join(Conversation, Presentation.conversation_id == Conversation.id)
                .filter(
                    Presentation.id == presentation_id,
                    Conversation.user_id == user_id
                )
                .first()
            )

            if not presentation:
                return None

            pages_data = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id
            ).order_by(PresentationPage.page_number.asc()).all()

            pages = [
                PageContent(
                    page_number=page_data.page_number,
                    html_content=page_data.html_content,
                    page_title=page_data.page_title,
                )
                for page_data in pages_data
            ]

            return {
                "id": str(presentation.id),
                "conversation_id": str(presentation.conversation_id),
                "topic": presentation.topic,
                "pages": pages,
                "total_pages": presentation.total_pages,
                "version": presentation.version,
                "metadata": presentation.pres_metadata or {},
                "created_at": presentation.created_at.isoformat() if presentation.created_at else None,
                "updated_at": presentation.updated_at.isoformat() if presentation.updated_at else None,
            }

        except Exception as e:
            logger.exception("load_presentation_failed")
            raise DatabaseError(f"Failed to load presentation: {e}") from e

    def update_presentation(
        self,
        presentation: PresentationDict,
        pages: List[PageContent],
        user_request: str,
        user_id: str,
    ) -> Optional[PresentationDict]:
        """
        Update presentation (archives current version, then updates).

        Args:
            presentation: Presentation dict with id, topic, total_pages
            pages: New list of PageContent objects
            user_request: User's request text
            user_id: UUID of the user (for ownership check)

        Returns:
            Presentation dict with updated version if successful, None otherwise
        """
        try:
            presentation_id = presentation["id"]

            if not presentation_id:
                return None

            current_presentation = (
                self.db.query(Presentation)
                .join(Conversation, Presentation.conversation_id == Conversation.id)
                .filter(
                    Presentation.id == presentation_id,
                    Conversation.user_id == user_id
                )
                .first()
            )

            if not current_presentation:
                return None

            current_version = current_presentation.version
            new_version = current_version + 1

            # Archive current version
            current_pages = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id
            ).all()

            if current_pages:
                old_user_request = None
                if current_presentation.pres_metadata:
                    old_user_request = current_presentation.pres_metadata.get("user_request")

                archived_version = PresentationVersion(
                    presentation_id=presentation_id,
                    version=current_version,
                    total_pages=current_presentation.total_pages,
                    user_request=old_user_request
                )
                self.db.add(archived_version)
                self.db.flush()

                for page in current_pages:
                    archived_page = PresentationVersionPage(
                        version_id=archived_version.id,
                        page_number=page.page_number,
                        html_content=page.html_content,
                        page_title=page.page_title
                    )
                    self.db.add(archived_page)

            # Delete old pages (will be replaced)
            self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id
            ).delete()

            # Update presentation metadata
            current_presentation.topic = presentation["topic"]
            current_presentation.total_pages = presentation["total_pages"]
            current_presentation.version = new_version
            current_presentation.pres_metadata = {"user_request": user_request}

            for page in pages:
                new_page = PresentationPage(
                    presentation_id=presentation_id,
                    page_number=page.page_number,
                    html_content=page.html_content,
                    page_title=page.page_title
                )
                self.db.add(new_page)

            self.db.commit()
            self.db.refresh(current_presentation)

            return {
                "id": str(current_presentation.id),
                "conversation_id": str(current_presentation.conversation_id),
                "topic": current_presentation.topic,
                "total_pages": current_presentation.total_pages,
                "version": current_presentation.version,
                "metadata": current_presentation.pres_metadata,
                "created_at": current_presentation.created_at.isoformat() if current_presentation.created_at else None,
                "updated_at": current_presentation.updated_at.isoformat() if current_presentation.updated_at else None,
            }

        except Exception as e:
            logger.exception("update_presentation_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to update presentation: {e}") from e

    def get_presentation_versions(
        self, presentation_id: str, user_id: str
    ) -> List[PresentationVersionDict]:
        """
        Get all versions metadata for a presentation.

        Args:
            presentation_id: UUID of presentation
            user_id: UUID of the user (for ownership check)

        Returns:
            List of PresentationVersion dicts
        """
        try:
            presentation = (
                self.db.query(Presentation)
                .join(Conversation, Presentation.conversation_id == Conversation.id)
                .filter(
                    Presentation.id == presentation_id,
                    Conversation.user_id == user_id
                )
                .first()
            )

            if not presentation:
                return []

            archived_versions = self.db.query(PresentationVersion).filter(
                PresentationVersion.presentation_id == presentation_id
            ).order_by(PresentationVersion.version.desc()).all()

            versions: List[PresentationVersionDict] = []

            # Current version first
            versions.append(
                {
                    "version": presentation.version,
                    "total_pages": presentation.total_pages,
                    "is_current": True,
                    "created_at": presentation.updated_at.isoformat() if presentation.updated_at else None,
                    "user_request": presentation.pres_metadata.get("user_request") if presentation.pres_metadata else None,
                }
            )

            for v in archived_versions:
                versions.append(
                    {
                        "version": v.version,
                        "total_pages": v.total_pages,
                        "is_current": False,
                        "created_at": v.created_at.isoformat() if v.created_at else None,
                        "user_request": v.user_request,
                    }
                )

            return versions

        except Exception as e:
            logger.exception("get_presentation_versions_failed")
            raise DatabaseError(f"Failed to get presentation versions: {e}") from e

    def get_version_content(
        self, presentation_id: str, version: int, user_id: str
    ) -> Optional[VersionContent]:
        """
        Get pages content of a specific version.

        Args:
            presentation_id: UUID of presentation
            version: Version number
            user_id: UUID of the user (for ownership check)

        Returns:
            VersionContent dict with pages and total_pages, or None
        """
        try:
            presentation = (
                self.db.query(Presentation)
                .join(Conversation, Presentation.conversation_id == Conversation.id)
                .filter(
                    Presentation.id == presentation_id,
                    Conversation.user_id == user_id
                )
                .first()
            )

            if not presentation:
                return None

            current_version = presentation.version

            if version == current_version:
                pages_data = self.db.query(PresentationPage).filter(
                    PresentationPage.presentation_id == presentation_id
                ).order_by(PresentationPage.page_number.asc()).all()
            else:
                archived_version = self.db.query(PresentationVersion).filter(
                    PresentationVersion.presentation_id == presentation_id,
                    PresentationVersion.version == version
                ).first()

                if not archived_version:
                    return None

                pages_data = self.db.query(PresentationVersionPage).filter(
                    PresentationVersionPage.version_id == archived_version.id
                ).order_by(PresentationVersionPage.page_number.asc()).all()

            if not pages_data:
                return None

            pages = [
                PageContent(
                    page_number=page_data.page_number,
                    html_content=page_data.html_content,
                    page_title=page_data.page_title,
                )
                for page_data in pages_data
            ]

            return {"pages": pages, "total_pages": len(pages)}

        except Exception as e:
            logger.exception("get_version_content_failed")
            raise DatabaseError(f"Failed to get version content: {e}") from e

    def get_active_presentation(self, conversation_id: str, user_id: str) -> Optional[str]:
        """
        Get active presentation ID for a conversation.

        Args:
            conversation_id: UUID of conversation
            user_id: UUID of the user (for ownership check)

        Returns:
            presentation_id or None
        """
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            ).first()

            if not conversation or not conversation.active_presentation_id:
                return None

            return str(conversation.active_presentation_id)

        except Exception as e:
            logger.exception("get_active_presentation_failed")
            raise DatabaseError(f"Failed to get active presentation: {e}") from e

    def set_active_presentation(
        self, conversation_id: str, presentation_id: str, user_id: str
    ) -> bool:
        """
        Set active presentation for a conversation.

        Args:
            conversation_id: UUID of conversation
            presentation_id: UUID of presentation
            user_id: UUID of the user (for ownership check)

        Returns:
            True if successful
        """
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            ).first()

            if not conversation:
                return False

            conversation.active_presentation_id = presentation_id
            self.db.commit()
            return True

        except Exception as e:
            logger.exception("set_active_presentation_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to set active presentation: {e}") from e

    def list_presentations(self, conversation_id: str, user_id: str) -> List[PresentationDict]:
        """
        List all presentations for a conversation.

        Args:
            conversation_id: UUID of conversation
            user_id: UUID of the user (for ownership check)

        Returns:
            List of Presentation dicts (without pages)
        """
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            ).first()

            if not conversation:
                return []

            presentations_data = self.db.query(Presentation).filter(
                Presentation.conversation_id == conversation_id
            ).order_by(Presentation.created_at.desc()).all()

            if not presentations_data:
                return []

            return [
                {
                    "id": str(p.id),
                    "conversation_id": str(p.conversation_id),
                    "topic": p.topic,
                    "total_pages": p.total_pages,
                    "version": p.version,
                    "metadata": p.pres_metadata,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in presentations_data
            ]

        except Exception as e:
            logger.exception("list_presentations_failed")
            raise DatabaseError(f"Failed to list presentations: {e}") from e
