from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, Branch, ApprovalRequest, AuditLog
from .serializers import (
    UserSerializer, BranchSerializer, ApprovalRequestSerializer, AuditLogSerializer,
)
from .permissions import IsFinance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username
        token['full_name'] = user.get_full_name()
        token['branch'] = user.branch.name if user.branch else None
        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'location']


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().select_related('branch')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'branch', 'department', 'is_active_employee']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'employee_id']

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFinance])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        new_password = request.data.get('password')
        if not new_password:
            return Response({'error': 'Password required'}, status=400)
        user.set_password(new_password)
        user.save()
        return Response({'status': 'Password reset'})


class ApprovalRequestViewSet(viewsets.ModelViewSet):
    queryset = ApprovalRequest.objects.all().select_related('requester', 'approver')
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['module', 'status', 'reference_id', 'approver']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        approval = self.get_object()
        if approval.status != 'PENDING':
            return Response({'error': 'Already processed'}, status=400)
        approval.status = 'APPROVED'
        approval.approver = request.user
        approval.comments = request.data.get('comments', '')
        approval.save()
        AuditLog.objects.create(
            user=request.user, action='APPROVE', module=approval.module,
            reference_id=approval.reference_id, details={'comments': approval.comments},
        )
        return Response(ApprovalRequestSerializer(approval).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        approval = self.get_object()
        if approval.status != 'PENDING':
            return Response({'error': 'Already processed'}, status=400)
        approval.status = 'REJECTED'
        approval.approver = request.user
        approval.comments = request.data.get('comments', '')
        approval.save()
        AuditLog.objects.create(
            user=request.user, action='REJECT', module=approval.module,
            reference_id=approval.reference_id, details={'comments': approval.comments},
        )
        return Response(ApprovalRequestSerializer(approval).data)

    @action(detail=False, methods=['get'])
    def my_pending(self, request):
        qs = self.get_queryset().filter(status='PENDING', required_role=request.user.role)
        return Response(ApprovalRequestSerializer(qs, many=True).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['module', 'action', 'user']