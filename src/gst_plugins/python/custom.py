import gi

gi.require_version("Gst", "1.0")
gi.require_version("GObject", "2.0")
from gi.repository import Gst  # type: ignore

VipipeCustomMeta = Gst.meta_register_custom(
    "VipipeCustomMeta",  # имя реализации
    ["vipipe", "custom"],  # теги для api_type_has_tag
    transform_func=None,  # None → копирование по умолчанию
    user_data=None,  # без доп. данных
)
