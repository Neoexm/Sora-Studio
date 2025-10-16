from importlib.resources import files, as_file
from PySide6.QtGui import QIcon

def icon(name: str) -> QIcon:
    res = files("sora_gui.assets.icons").joinpath(name)
    with as_file(res) as p:
        return QIcon(str(p))

def asset_path(*parts) -> str:
    res = files("sora_gui.assets").joinpath(*parts)
    with as_file(res) as p:
        return str(p)
