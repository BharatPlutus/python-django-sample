from celery import shared_task
from services.models.popular_service import PopularService
from services.serializers.popular_service import PopularServiceSerializer


@shared_task
def popular_service_count_increment(response):
    for item in response['items']:
        try:
            popular_service = PopularService.objects.get(service_id=item['price_group_service']["service_id"],
                                                         store_id=response['store']['id'])
        except Exception as err:
            payload = dict(service_id=item['price_group_service']["service_id"], count=1,
                           store_id=response['store']['id'])
            serializer = PopularServiceSerializer(data=payload)

            if serializer.is_valid():
                serializer.create(serializer.validated_data)
        else:
            popular_service.count = popular_service.count + 1
            popular_service.save()
