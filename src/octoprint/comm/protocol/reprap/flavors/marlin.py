__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 The OctoPrint Project - Released under terms of the AGPLv3 License"

import re

from octoprint.comm.protocol.reprap.flavors import StandardFlavor


class MarlinFlavor(StandardFlavor):

    key = "marlin"
    name = "Marlin"

    emergency_commands = ["M112", "M108", "M410"]
    heatup_abortable = True

    regex_marlin_kill_error = re.compile(
        r"Heating failed|Thermal Runaway|MAXTEMP triggered|MINTEMP triggered|Invalid extruder number|Watchdog barked|KILL caused"
    )
    """Regex matching first line of kill causing errors from Marlin."""

    def comm_error(self, line, lower_line):
        result = super().comm_error(line, lower_line)

        if self.regex_min_max_error.match(line):
            self._protocol.internal_state.multiline_error = line

        return result


class MarlinLegacyFlavor(StandardFlavor):

    key = "marlinlegacy"
    name = "Legacy Marlin"

    @classmethod
    def identifier(cls, firmware_name, firmware_info):
        return "marlin v1" in firmware_name.lower()


class PrusaMarlinFlavor(MarlinFlavor):

    key = "prusamarlin"
    name = "Marlin: Prusa variant"

    @classmethod
    def identifier(cls, firmware_name, firmware_info):
        return (
            "prusa-firmware" in firmware_name.lower()
            and "marlin" in firmware_name.lower()
        )