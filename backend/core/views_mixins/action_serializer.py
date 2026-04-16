class ActionSerializerMixin:
    def get_serializer_class(self):
        return self.serializer_class[self.action]
