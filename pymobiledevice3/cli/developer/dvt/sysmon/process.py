import logging
from collections import namedtuple
from typing import Annotated

import typer
from typer_di import TyperDI

from pymobiledevice3.cli.cli_common import ServiceProviderDep, print_json
from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
from pymobiledevice3.services.dvt.instruments.device_info import DeviceInfo
from pymobiledevice3.services.dvt.instruments.sysmontap import Sysmontap

logger = logging.getLogger(__name__)


cli = TyperDI(
    name="process",
    help="Process monitor options.",
    no_args_is_help=True,
)


@cli.command("monitor")
def sysmon_process_monitor(service_provider: ServiceProviderDep, threshold: float) -> None:
    """monitor all most consuming processes by given cpuUsage threshold."""

    Process = namedtuple("process", "pid name cpuUsage physFootprint")

    with DvtSecureSocketProxyService(lockdown=service_provider) as dvt, Sysmontap(dvt) as sysmon:
        for process_snapshot in sysmon.iter_processes():
            entries = []
            for process in process_snapshot:
                if (process["cpuUsage"] is not None) and (process["cpuUsage"] >= threshold):
                    entries.append(
                        Process(
                            pid=process["pid"],
                            name=process["name"],
                            cpuUsage=process["cpuUsage"],
                            physFootprint=process["physFootprint"],
                        )
                    )

            logger.info(entries)


@cli.command("single")
def sysmon_process_single(
    service_provider: ServiceProviderDep,
    attributes: Annotated[
        list[str] | None,
        typer.Option(
            "--attributes",
            "-a",
            help="filter processes by given attribute value given as key=value. Can be specified multiple times.",
        ),
    ] = None,
) -> None:
    """show a single snapshot of currently running processes."""

    count = 0

    result = []
    with DvtSecureSocketProxyService(lockdown=service_provider) as dvt:
        device_info = DeviceInfo(dvt)

        with Sysmontap(dvt) as sysmon:
            for process_snapshot in sysmon.iter_processes():
                count += 1

                if count < 2:
                    # first sample doesn't contain an initialized value for cpuUsage
                    continue

                for process in process_snapshot:
                    skip = False
                    if attributes is not None:
                        for filter_attr in attributes:
                            filter_attr, filter_value = filter_attr.split("=", 1)
                            if str(process[filter_attr]) != filter_value:
                                skip = True
                                break

                    if skip:
                        continue

                    # adding "artificially" the execName field
                    process["execName"] = device_info.execname_for_pid(process["pid"])
                    result.append(process)

                # exit after single snapshot
                break

    print_json(result)
