try:
    import sbslibs
    from sbs_utils.handlerhooks import *
    from sbs_utils.gui import Gui
    from sbs_utils.mast.maststorypage import StoryPage
    from sbs_utils.mast.mast import Mast

    class VisualRangePage(StoryPage):
        story_file = "story.mast"
        # No main_server / main_client override: the LM consoles addon reroutes the server to
        # its mission picker and clients to its console select, which is where the range's map
        # selection comes from. Overriding these is what bypassed it.

    Mast.include_code = True   # show MAST source in runtime errors

    Gui.server_start_page_class(VisualRangePage)
    Gui.client_start_page_class(VisualRangePage)
except Exception as e:
    message = e
    def cosmos_event_handler(sim, event):
        import sbs
        sbs.send_gui_clear(event.client_id, "")
        sbs.send_gui_text(event.client_id, "", "text",
                          f"$text:sbs_utils runtime error^{message};", 0, 0, 80, 95)
        sbs.send_gui_complete(event.client_id, "")
