#!/usr/bin/env python3
import sys
import time
import logging
from logging import getLogger


# debugger modules
from pyedbglib.hidtransport.hidtransportfactory import hid_transport
from pyedbglib.protocols import housekeepingprotocol
from pyedbglib.protocols.avr8protocol import Avr8Protocol
from pymcuprog.backend import Backend
from pymcuprog.toolconnection import ToolUsbHidConnection
from pymcuprog.avr8target import MegaAvrJtagTarget
from pymcuprog.utils import read_tool_info

# Chip to connect to
from atmega644 import DEVICE_INFO
#from atmega324pb import DEVICE_INFO # XplainedPro board

logger = None
target = None

class NewMegaAvrJtagTarget(MegaAvrJtagTarget):
    
    def setup_config(self, device_info):
        """
        Sets up the configuration for a debug session"
        """
        # Extract settings
        fl_page_size = device_info.get('flash_page_size_bytes')
        fl_size = device_info.get('flash_size_bytes')
        fl_base = device_info.get('flash_address_byte')
        sram_base = device_info.get('internal_sram_address_byte')
        ee_page_size = device_info.get('eeprom_page_size_bytes')
        ee_size = device_info.get('eeprom_size_bytes')
        ocd_addr = device_info.get('ocd_base')
        ocd_rev = device_info.get('ocd_rev')
        pagebuffers_per_flash_block = device_info.get('buffers_per_flash_page',1)
        eear_size = device_info.get('eear_size')
        eearh_addr = device_info.get('eear_base') + eear_size - 1
        eearl_addr = device_info.get('eear_base')
        eecr_addr = device_info.get('eecr_base')
        eedr_addr = device_info.get('eedr_base')
        spmcsr_addr = device_info.get('spmcsr_base')
        osccal_addr = device_info.get('osccal_base') 
    
        # Setup device structure and write to tool
    
        # TMEGA_FLASH_PAGE_BYTES (2@0x00)
        devdata = bytearray([fl_page_size & 0xff, (fl_page_size >> 8) & 0xff])
        # TMEGA_FLASH_BYTES (4@0x02)
        devdata += bytearray([fl_size & 0xFF, (fl_size >> 8) & 0xFF,
                                (fl_size >> 16) & 0xFF, (fl_size >> 24) & 0xFF])
        # TMEGA_FLASH_BASE (4@0x06)
        devdata += bytearray([fl_base & 0xFF, (fl_base >> 8) & 0xFF,
                                (fl_base >> 16) & 0xFF, (fl_base >> 24) & 0xFF])
        # TMEGA_BOOT_BASE (4@0x0A)
        boot_base = fl_size - fl_page_size # as is done for MegaAvr
        devdata += bytearray([boot_base & 0xFF, (boot_base >> 8) & 0xFF,
                                (boot_base >> 16) & 0xFF, (boot_base >> 24) & 0xFF])
        # TMEGA_SRAM_BASE (2@0x0E)
        devdata += bytearray([sram_base & 0xff, (sram_base >> 8) & 0xff])
        # TMEGA_EEPROM_BYTES (2@0x10)
        devdata += bytearray([ee_size & 0xff, (ee_size >> 8) & 0xff])
        # TMEGA_EEPROM_PAGE_BYTES (1@0x12)
        devdata += bytearray([ee_page_size])
        # TMEGA_OCD_REVISION (1@0x13)
        devdata += bytearray([ocd_rev])
        # TMEGA_PAGEBUFFERS_PER_FLASH_BLOCK
        devdata += bytearray([pagebuffers_per_flash_block])
        # 3 byte gap (3@0x15)
        devdata += bytearray([0, 0, 0])
        # TMEGA_OCD_MODULE_ADDRESS (1@0x18)
        devdata += bytearray([ocd_addr & 0xff])
        # TMEGA_EEARH_BASE (1@0x19)
        devdata += bytearray([eearh_addr & 0xFF])
        # TMEGA_EEARL_BASE (1@0x1A)
        devdata += bytearray([eearl_addr & 0xFF])
        # TMEGA_EECR_BASE (1@0x1B)
        devdata += bytearray([eecr_addr & 0xFF])
        # TMEGA_EEDR_BASE (1@0x1C)
        devdata += bytearray([eedr_addr & 0xFF])
        # TMEGA_SPMCSR_BASE (1@0x1D)
        devdata += bytearray([spmcsr_addr & 0xFF])
        # TMEGA_OSCCAL_BASE (1@0x1E)
        devdata += bytearray([osccal_addr & 0xFF])

        self.logger.info("Write all device data: %s",
                              [devdata.hex()[i:i+2] for i in range(0, len(devdata.hex()), 2)])
        self.protocol.write_device_data(devdata)


    def setup_debug_session(self):
        """
        Sets up a debugging session on an Mega AVR (JTAG)
        """
        self.protocol.set_variant(Avr8Protocol.AVR8_VARIANT_MEGAOCD)
        self.protocol.set_function(Avr8Protocol.AVR8_FUNC_DEBUGGING)
        #self.protocol.set_function(Avr8Protocol.AVR8_FUNC_PROGRAMMING)
        self.protocol.set_interface(Avr8Protocol.AVR8_PHY_INTF_JTAG)

def hid_connect(logger):
    """
    Connect to a tool. It should be the only one connected to the desktop.
    The function returns a transport instance.
    """
    try:
        backend = Backend()
        toolconnection = ToolUsbHidConnection(serialnumber=None, tool_name=None)
        backend.connect_to_tool(toolconnection)
        backend.disconnect_from_tool()
    
        transport = hid_transport()
        transport.connect(serial_number=toolconnection.serialnumber,
                            product=toolconnection.tool_name)
        return transport
    except Exception as e:
        logger.critical("Could not connect to any hardware debugger")
        return None

def read_signature():
    """
    Read signature, which is only allowed in programming mode
    """
    global target, logger
    logger.info("Reading signature")
    return target.protocol.memory_read(Avr8Protocol.AVR8_MEMTYPE_SIGNATURE, 0, 3)


def read_sram():
    """
    Read a from SRAM, which is only allowed in debugging mode
    """
    global target, logger
    logger.info("Reading from SRAM")
    return target.protocol.memory_read(Avr8Protocol.AVR8_MEMTYPE_SRAM, 0x100, 2)

def main():
    global target, logger
    
    logging.basicConfig(stream=sys.stdout,level=logging.INFO)
    logger = getLogger()
    getLogger('pyedbglib.hidtransport.hidtransportbase').setLevel(logging.ERROR)
    logger.info("Starting test...")

    transport = hid_connect(logger)
    if transport is None:
        return 1

    logger.info("Connected to %s", transport.hid_device.get_product_string())
    logger.info("Trying to connect to JTAG MCU %s ...", DEVICE_INFO['name'])

    hk = housekeepingprotocol.Jtagice3HousekeepingProtocol(transport)
    hk.start_session()
    logger.info("Housekeeping session started")

    target = NewMegaAvrJtagTarget(transport)
    logger.info("Target class instantiated")

    target.setup_debug_session()
    logger.info("Debug session prepared")

    target.setup_config(DEVICE_INFO)
    logger.info("Configuration sent to tool")

    resp = target.activate_physical()
    logger.info("Physcial connection activated")
    logger.info("JTAG ID read: %02X%02X%02X%02X", resp[3], resp[2], resp[1], resp[0])

    #target.protocol.attach()
    #logger.info("Attached to OCD")

    #target.protocol.reset()
    #logger.info("MCU stopped")


    target.protocol.enter_progmode()
    logger.info("Programming mode entered")

    read_signature()
    
    target.protocol.leave_progmode()
    logger.info("Programming mode stopped")

    read_sram()

    target.protocol.enter_progmode()
    logger.info("Programming mode entered")

    read_signature()
    
    target.protocol.leave_progmode()
    logger.info("Programming mode stopped")

    read_sram()

    target.protocol.enter_progmode()
    logger.info("Programming mode entered")
    
    read_signature()
    
    target.protocol.leave_progmode()
    logger.info("Programming mode stopped")


    #target.protocol.attach()
    #logger.info("Attached to OCD")

    target.protocol.reset()
    logger.info("MCU stopped")

    read_sram()

    target.protocol.stop()
    logger.info("AVR core stopped")

    target.protocol.detach()
    logger.info("Detached from OCD")

    target.deactivate_physical()
    logger.info("Physcial connection deactivated")

    hk.end_session()
    logger.info("Housekeeping session stopped")
    return 0
    
 
    
    
if __name__ == "__main__":
    sys.exit(main())
