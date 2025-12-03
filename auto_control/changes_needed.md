# Changes to make:

- Illumination active during while load-unload procedure. Ignore 30s rule during load-unload. Done.
- Error on finish of load_unload procedure, left load-lock gate valve open. Eliminate that.
- Ensure that safety_checks are done for auto_procedures, test all.
- Still issues with the GasFLowCOntroller. When init it can stop the mouse from working. Possibly due to threading. Try to fix that.
- Check the port searching logic in serial connection modules. We should just have a setup script that finds th eports and saves them to a config file, rather than trying to scan all ports every time we start up. This is causing issues with other USB devices (like mouse).
- Add short sleeps after serial commands to avoid overwhelming the serial buffers.