try:
    import sbslibs
    from sbs_utils.handlerhooks import *
    from sbs_utils.gui import Gui
    from sbs_utils.mast.maststorypage import StoryPage
    from sbs_utils.mast.mast import Mast

    class VisualRangePage(StoryPage):
        story_file = "story.mast"
        # The server drives the range (picker + scene building); a client is only ever a
        # viewport onto the specimen, so the two start at different labels.
        main_server = "visual_server_start"
        main_client = "visual_client_start"

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
