from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EnquiryViewSet, PreliminaryGAViewSet, QuotationViewSet,
    OfferSubmissionViewSet, FollowUpDiscussionViewSet,
    ClientPOViewSet, ProjectReviewViewSet,
)

router = DefaultRouter()
router.register('enquiries', EnquiryViewSet)
router.register('ga-drawings', PreliminaryGAViewSet)
router.register('quotations', QuotationViewSet)
router.register('offer-submissions', OfferSubmissionViewSet)
router.register('follow-ups', FollowUpDiscussionViewSet)
router.register('client-pos', ClientPOViewSet)
router.register('project-reviews', ProjectReviewViewSet)

urlpatterns = [path('', include(router.urls))]