### Test of attaching to a JTAG target OCD

Download, create a virtual Python environment, and install requirements (in requirements.txt) with pip. Then start test.py. 

Works perfectly for ATmega164PA (and other Megas) on Atmel-ICE, JTAGICE3, Power debugger, and EDBG (on ATmega324BP Xplained Pro), but has problems on SNAP and PICkit4. Apparently, for the latter two, the debugger state machine does not work as described in Section 7.5 of *Embedded Debugger-Based Tools Protocols User's Guide*. After reading this section, I pictured the state machine as follows.

![](debug_fsm.png)

And this seems to be what is implemented in Atmel-ICE, JTAG-ICE, and others. One might be able to draw another FSM for SNAP and PICkit4, but it would definitely be less regular. In any case, the only safe way to switch between programming mode and debugging mode is to force a restart of the session by using `deactivate_physical` followed by `activate_physical`. Further, since the `attach` call often also leads to problems, i.e., one does not end up in debugging mode, one should enter debug mode using `enter_progmode` followed by `leave_progmode`.

