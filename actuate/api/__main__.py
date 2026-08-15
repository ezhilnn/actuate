"""python -m actuate.api"""

from actuate.runtime_loop import configure_windows_selector_loop

configure_windows_selector_loop()

from actuate.api.app import run

if __name__ == "__main__":
    run()
