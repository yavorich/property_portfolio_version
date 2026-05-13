import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.listings.models import Listing, ListingPhoto

logger = logging.getLogger(__name__)

CLEANUP_AGE = timedelta(days=30)


@shared_task(name="apps.listings.cleanup_old_media")
def cleanup_old_media() -> dict:
    """Delete photos and presentation PDFs of listings older than 30 days.

    The ``Listing`` row itself is kept (for history / admin); only its
    file artefacts on disk are removed and the FileField references nulled.
    """
    threshold = timezone.now() - CLEANUP_AGE
    stale = Listing.objects.filter(created_at__lt=threshold).exclude(
        photos__original="", presentation=""
    )

    photos_removed = 0
    pdfs_removed = 0
    for listing in stale.iterator(chunk_size=50):
        for photo in listing.photos.all():
            if photo.original:
                photo.original.delete(save=False)
                photos_removed += 1
            if photo.processed:
                photo.processed.delete(save=False)
                photos_removed += 1
            photo.save(update_fields=["original", "processed"])
        if listing.presentation:
            listing.presentation.delete(save=False)
            pdfs_removed += 1
            listing.save(update_fields=["presentation"])

    logger.info(
        "cleanup_old_media: removed %d photo files, %d PDFs (threshold=%s)",
        photos_removed, pdfs_removed, threshold,
    )
    return {"photos_removed": photos_removed, "pdfs_removed": pdfs_removed}
