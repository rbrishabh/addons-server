from rest_framework import serializers

from olympia import amo
from olympia.abuse.models import AbuseReport
from olympia.accounts.serializers import BaseUserSerializer
from olympia.api.fields import ReverseChoiceField


class BaseAbuseReportSerializer(serializers.ModelSerializer):
    reporter = BaseUserSerializer(read_only=True)

    class Meta:
        model = AbuseReport
        fields = ('message', 'reporter')

    def validate_target(self, data, target_name):
        if target_name not in data:
            msg = serializers.Field.default_error_messages['required']
            raise serializers.ValidationError({
                target_name: [msg]
            })

    def to_internal_value(self, data):
        output = super(BaseAbuseReportSerializer, self).to_internal_value(data)
        request = self.context['request']
        output['country_code'] = AbuseReport.lookup_country_code_from_ip(
            request.META.get('REMOTE_ADDR'))
        if request.user.is_authenticated:
            output['reporter'] = request.user
        return output


class AddonAbuseReportSerializer(BaseAbuseReportSerializer):
    addon = serializers.SerializerMethodField()
    reason = ReverseChoiceField(
        choices=list(AbuseReport.REASONS.api_choices), required=False,
        allow_null=True)
    # 'message' has custom validation rules below depending on whether 'reason'
    # was provided or not. We need to not set it as required and allow blank at
    # the field level to make that work.
    message = serializers.CharField(
        required=False, allow_blank=True, max_length=10000)
    app = ReverseChoiceField(
        choices=list((v.id, k) for k, v in amo.APPS.items()), required=False,
        source='application')
    appversion = serializers.CharField(
        required=False, source='application_version', max_length=255)
    lang = serializers.CharField(
        required=False, source='application_locale', max_length=255)
    report_entry_point = ReverseChoiceField(
        choices=list(AbuseReport.REPORT_ENTRY_POINTS.api_choices),
        required=False, allow_null=True)
    addon_install_method = ReverseChoiceField(
        choices=list(AbuseReport.ADDON_INSTALL_METHODS.api_choices),
        required=False, allow_null=True)
    addon_signature = ReverseChoiceField(
        choices=list(AbuseReport.ADDON_SIGNATURES.api_choices),
        required=False, allow_null=True)

    class Meta:
        model = AbuseReport
        fields = BaseAbuseReportSerializer.Meta.fields + (
            'addon',
            'addon_install_method',
            'addon_install_origin',
            'addon_name',
            'addon_signature',
            'addon_summary',
            'addon_version',
            'app',
            'appversion',
            'client_id',
            'install_date',
            'lang',
            'operating_system',
            'operating_system_version',
            'reason',
            'report_entry_point'
        )

    def validate(self, data):
        if not data.get('reason'):
            # If reason is not provided, message is required and can not be
            # null or blank.
            message = data.get('message')
            if not message:
                if 'message' not in data:
                    msg = serializers.Field.default_error_messages['required']
                elif message is None:
                    msg = serializers.Field.default_error_messages['null']
                else:
                    msg = serializers.CharField.default_error_messages['blank']
                raise serializers.ValidationError({
                    'message': [msg]
                })
        return data

    def to_internal_value(self, data):
        self.validate_target(data, 'addon')
        view = self.context.get('view')
        output = view.get_guid_and_addon()
        # Pop 'addon' from data before passing that data to super(), we already
        # have it in the output value.
        data.pop('addon')
        output.update(
            super(AddonAbuseReportSerializer, self).to_internal_value(data)
        )
        return output

    def get_addon(self, obj):
        addon = obj.addon
        if not addon and not obj.guid:
            return None
        return {
            'guid': addon.guid if addon else obj.guid,
            'id': addon.id if addon else None,
            'slug': addon.slug if addon else None,
        }


class UserAbuseReportSerializer(BaseAbuseReportSerializer):
    user = BaseUserSerializer(required=False)  # We validate it ourselves.
    # Unlike add-on reports, for user reports we don't have a 'reason' field so
    # the message is always required and can't be blank.
    message = serializers.CharField(
        required=True, allow_blank=False, max_length=10000)

    class Meta:
        model = AbuseReport
        fields = BaseAbuseReportSerializer.Meta.fields + (
            'user',
        )

    def to_internal_value(self, data):
        view = self.context.get('view')
        self.validate_target(data, 'user')
        output = {
            'user': view.get_user_object()
        }
        # Pop 'user' before passing it to super(), we already have the
        # output value and did the validation above.
        data.pop('user')
        output.update(
            super(UserAbuseReportSerializer, self).to_internal_value(data)
        )
        return output
