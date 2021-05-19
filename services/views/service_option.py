from django.db import transaction
from rest_framework.generics import DestroyAPIView
from rest_framework.permissions import IsAuthenticated

from common_config.api_code import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_OK, HTTP_400_BAD_REQUEST
from common_config.api_message import DELETE_SERVICE_OPTION, DELETE_SERVICE_OPTION_LOGIC, \
    DELETE_SERVICE_OPTION_IMAGE, INVALID_SERVICE_OPTION_MATCH_QUERY, INVALID_SERVICE_OPTION_IMAGE_ID
from common_config.logger.logging_handler import logger
from common_config.http import Http404
from utils.api_response import APIResponse
from utils.permissions import IsAuthorized

from services.models.service_option import ServiceOption
from services.models.service_option_logic import ServiceOptionAction, ServiceOptionRule
from services.serializers.service import ServiceViewSerializer
from services.serializers.service_option import ServiceOptionUpdateSerializer


class ServiceOptionDestroyView(DestroyAPIView):
    """
    An Api View which provides a method to delete service option.
    Accepts the following DELETE header parameters: access token
    Returns the success/fail message.
    """
    queryset = ServiceOption.objects.all()
    serializer_class = ServiceOptionUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('delete_serviceoption',)
    lookup_field = ("service_id", "pk")

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {}

        # Perform the lookup filtering.
        for field in self.lookup_field:
            filter_kwargs[field] = self.kwargs[field]

        try:
            return queryset.get(**filter_kwargs)
        except queryset.model.DoesNotExist:
            raise Http404(detail=INVALID_SERVICE_OPTION_MATCH_QUERY.format(self.kwargs['service_id'],
                                                                           self.kwargs['pk']), attr_name="message")

    @staticmethod
    def filter_and_get_object(model_klass, search_id, attr_name):
        kwargs = {attr_name: search_id}
        return model_klass.objects.filter(**kwargs)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # validate service and service option id and get object
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # delete service option
            instance.delete()

            # delete service option logic
            option_actions = self.filter_and_get_object(ServiceOptionAction, instance.id, "apply_to_option_id")

            for action in option_actions:
                # get all action rules
                rules = action.rules.all()
                for rule in rules:
                    # delete rule
                    rule.delete()

                # delete action
                action.delete()

            if len(option_actions) <= 0:
                delete_ids = []

                option_rules = self.filter_and_get_object(ServiceOptionRule, instance.id, "compare_option_field")

                for rule in option_rules:
                    if rule.option_action_id not in delete_ids:
                        delete_ids.append(rule.option_action_id)

                    # delete rule
                    rule.delete()

                for obj in delete_ids:
                    # delete action
                    obj.delete()

        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while delete service option
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_500_INTERNAL_SERVER_ERROR)

        # convert model object into json
        data = ServiceViewSerializer(instance.service_id).data
        data['message'] = DELETE_SERVICE_OPTION

        return APIResponse(data, HTTP_OK)


class ServiceOptionLogicDestroyView(DestroyAPIView):
    """
    An Api View which provides a method to delete service option logic.
    Accepts the following DELETE header parameters: access token
    Returns the success/fail message.
    """
    queryset = ServiceOption.objects.all()
    serializer_class = ServiceOptionUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('delete_serviceoptionaction',)
    lookup_field = ("service_id", "pk")

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {}

        # Perform the lookup filtering.
        for field in self.lookup_field:
            filter_kwargs[field] = self.kwargs[field]

        try:
            return queryset.get(**filter_kwargs)
        except queryset.model.DoesNotExist:
            raise Http404(detail=INVALID_SERVICE_OPTION_MATCH_QUERY.format(self.kwargs['service_id'],
                                                                           self.kwargs['pk']), attr_name="message")

    @staticmethod
    def filter_and_get_object(model_klass, search_id, attr_name):
        kwargs = {attr_name: search_id}
        return model_klass.objects.filter(**kwargs)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # validate and get object
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # delete service option logic
            option_actions = self.filter_and_get_object(ServiceOptionAction, instance.id, "apply_to_option_id")

            for action in option_actions:
                # get all action rules
                rules = action.rules.all()
                for rule in rules:
                    # delete rule
                    rule.delete()

                # delete action
                action.delete()

            if len(option_actions) <= 0:
                delete_ids = []

                option_rules = self.filter_and_get_object(ServiceOptionRule, instance.id, "compare_option_field")

                for rule in option_rules:
                    if rule.option_action_id not in delete_ids:
                        delete_ids.append(rule.option_action_id)

                    # delete rule
                    rule.delete()

                for obj in delete_ids:
                    # delete action
                    obj.delete()

        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while delete service option login
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_500_INTERNAL_SERVER_ERROR)

        return APIResponse({'message': DELETE_SERVICE_OPTION_LOGIC}, HTTP_OK)


class ServiceOptionImageDestroyView(DestroyAPIView):
    """
    An Api View which provides a method to delete service option image.
    Accepts the following DELETE header parameters: access token
    Returns the success/fail message.
    """
    queryset = ServiceOption.objects.all()
    serializer_class = ServiceOptionUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('delete_image',)
    lookup_field = ("service_id", "pk", "image_id",)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {}

        # Perform the lookup filtering.
        for field in ['service_id', 'pk']:
            filter_kwargs[field] = self.kwargs[field]

        try:
            return queryset.get(**filter_kwargs)
        except queryset.model.DoesNotExist as err:
            raise Http404(detail=INVALID_SERVICE_OPTION_MATCH_QUERY.format(self.kwargs['service_id'],
                                                                           self.kwargs['pk']), attr_name="message")

    def delete(self, request, *args, **kwargs):
        # validate and get object
        instance = self.get_object()

        image_id = self.kwargs['image_id']

        # get service option image
        image = instance.images.filter(id=image_id)

        if len(image) <= 0:
            return APIResponse({'message': INVALID_SERVICE_OPTION_IMAGE_ID.format(image_id)}, HTTP_400_BAD_REQUEST)

        try:
            # delete service option image reference relationship table
            instance.images.remove(image_id)

            # delete image
            image[0].delete_image()

        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            return APIResponse({"message": err.args[0]}, HTTP_500_INTERNAL_SERVER_ERROR)

        return APIResponse({'message': DELETE_SERVICE_OPTION_IMAGE}, HTTP_OK)
