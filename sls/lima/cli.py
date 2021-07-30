import struct
import asyncio
import contextlib
import urllib.parse

import click
import Lima.Core
from beautifultable import BeautifulTable
from limatb.cli import camera, url, table_style, max_width
from limatb.info import info_list
from limatb.network import get_subnet_addresses, get_host_by_addr

from .camera import Interface
from ..client import Detector
from ..protocol import (DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT, DetectorType,
                        CommandCode, ResultType, decode_update_client)


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


async def test_communication(address, port):
    request = struct.pack('<i', CommandCode.DETECTOR_TYPE)
    reader, writer = await asyncio.open_connection(address, port)
    with contextlib.closing(writer):
        writer.write(request)
        await writer.drain()
        data = await reader.readexactly(2*4)
        result, dtype = struct.unpack('<ii', data)
        assert result != ResultType.FAIL
        dtype = DetectorType(dtype)

    request = struct.pack('<i', CommandCode.UPDATE_CLIENT)
    reader, writer = await asyncio.open_connection(address, port)
    with contextlib.closing(writer):
        writer.write(request)
        await writer.drain()
        data = await reader.readexactly(100)
        result, *reply = struct.unpack('<i16siiiiiiqqqqqqq', data)
        assert result != ResultType.FAIL
        detector = decode_update_client(reply)
        detector['address'] = address
        detector['host'] = (await get_host_by_addr(address)).name
        detector['port'] = port
        detector['type'] = dtype
        return detector


async def find_detectors(port=DEFAULT_CTRL_PORT, timeout=2.0):
    detectors = []
    addresses = get_subnet_addresses()
    coros = [test_communication(address, port) for address in addresses]
    try:
        for task in asyncio.as_completed(coros, timeout=timeout):
            try:
                detector = await task
            except OSError:
                continue
            if detector is not None:
                detectors.append(detector)
    except asyncio.TimeoutError:
        pass
    return detectors


def detector_table(detectors):
    import beautifultable

    width = click.get_terminal_size()[0]
    table = beautifultable.BeautifulTable(max_width=width)
    table.column_headers = [
        'Host', 'IP', 'Port', 'Type', '#Modules', 'Settings', 'Threshold', 'Dyn. Range'
    ]
    for detector in detectors:
        table.append_row(
            (detector['host'],
             detector['address'],
             detector['port'],
             detector['type'].name,
             detector['nb_modules'],
             detector['settings'].name,
             detector['energy_threshold'],
             detector['dynamic_range'])
        )
    return table


async def scan(port=DEFAULT_CTRL_PORT, timeout=2.0):
    detectors = await find_detectors(port, timeout)
    return detector_table(detectors)


@mythensls.command("scan")
@click.option('-p', '--port', default=DEFAULT_CTRL_PORT)
@click.option('--timeout', default=2.0)
@table_style
@max_width
def mythen_scan(port, timeout, table_style, max_width):
    """show accessible sls detectors on the network"""
    table = asyncio.run(scan(port, timeout))
    style = getattr(table, "STYLE_" + table_style.upper())
    table.set_style(style)
    table.max_table_width = max_width
    click.echo(table)
