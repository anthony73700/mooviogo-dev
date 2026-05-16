from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from mooviogo.observability import emit_alert, emit_event

from .models import Report

User = get_user_model()


def send_report_moderation_notifications(report: Report, actor, action_name: str) -> int:
    """Notify parties impacted by a moderation decision."""
    recipients = set()

    if report.reporter and report.reporter.email:
        recipients.add(report.reporter.email)
    if report.assigned_moderator and report.assigned_moderator.email:
        recipients.add(report.assigned_moderator.email)

    if report.target_type == Report.TargetType.USER:
        target_user = User.objects.filter(id=report.target_id).only("email").first()
        if target_user and target_user.email:
            recipients.add(target_user.email)

    if not recipients:
        return 0

    actor_label = getattr(actor, "email", "admin")
    subject = f"[Mooviogo] Moderation signalement #{report.id}"
    lines = [
        "Une action de moderation a ete appliquee.",
        f"Signalement: #{report.id}",
        f"Action: {action_name}",
        f"Statut: {report.status}",
        f"Code resolution: {report.resolution_code}",
        f"Moderateur: {actor_label}",
    ]
    if report.moderation_notes:
        lines.append(f"Notes: {report.moderation_notes}")
    if report.sla_due_at:
        lines.append(f"SLA echeance: {report.sla_due_at.isoformat()}")
    if report.suspension_ends_at:
        lines.append(f"Fin suspension: {report.suspension_ends_at.isoformat()}")

    recipient_list = sorted(recipients)
    try:
        send_mail(
            subject=subject,
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        emit_event("reports.notifications.sent", report_id=report.id, recipients=len(recipient_list))
        return len(recipient_list)
    except Exception as exc:
        emit_alert(
            "reports.notifications.send_failed",
            severity="error",
            report_id=report.id,
            recipients=len(recipient_list),
            error=str(exc),
        )
        return 0
