from django.http import JsonResponse


def load_widget(widget_id):
    if not widget_id:
        raise ValueError('missing id')
    # pretend this hits a database
    raise RuntimeError('widget store unavailable')


def widget_detail(request, widget_id):
    try:
        widget = load_widget(widget_id)
        return JsonResponse({'id': widget_id, 'name': widget})
    except Exception as exc:
        # Swallow point: the exception is caught and converted to a 500 here, so
        # Django's exception machinery (and DjangoIntegration) never sees it.
        print('failed to load widget:', exc)
        return JsonResponse({'error': 'could_not_load_widget'}, status=500)
