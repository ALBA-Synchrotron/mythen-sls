import urllib.parse

import click
import Lima.Core
from beautifultable import BeautifulTable
from lima_toolbox.tool import camera, url
from lima_toolbox.info import info_list

from .camera import Interface
from ..client import Detector
from ..protocol import DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT


@camera(name="mythensls")
@url
@click.option('--stop-port', type=int)
@click.pass_context
def mythensls(ctx, url, stop_port):
    """SLS Mythen II detector specific commands"""
    if url is None:
        return
    if not url.startswith("tcp://"):
        url = "tcp://" + url
    url = urllib.parse.urlparse(url)
    if url.port is None:
        port = DEFAULT_CTRL_PORT
        if stop_port is None:
            stop_port = DEFAULT_STOP_PORT
    else:
        port = url.port
        if stop_port is None:
            stop_port = port + 1
    camera = Detector(url.hostname, ctrl_port=port, stop_port=stop_port)
    interface = Interface(camera)
    interface.camera = camera
    ctx.obj['camera'] = camera
    return interface


# override the default info that just shows lima info
@mythensls.command("info")
@click.pass_context
def info(ctx):
    camera = ctx.obj['camera']
    interface = ctx.obj['interface']
    lima_info = interface.getHwCtrlObj(Lima.Core.HwCap.DetInfo)
    table = BeautifulTable()
    table.set_style(table.STYLE_COMPACT)
    table.column_headers = ["name", "value"]
    table.column_alignments["name"] = table.ALIGN_RIGHT
    table.column_alignments["value"] = table.ALIGN_LEFT
    for item in info_list(lima_info):
        table.append_row(item)
    table.append_row(('', ''))
    for item in camera.dump().items():
        table.append_row(item)
    table.column_headers = ['', '']
    click.echo(table)

