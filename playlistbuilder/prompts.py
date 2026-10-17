def ask(prompt, choices):
    ans = ""
    while ans not in choices:
        ans = input(prompt).strip().lower()
    return ans


def ask_quit_choice():
    """After q: keep the session for later, or end it here. Returns 'c' or 'e'."""
    return ask("Come back to this later, or end the session here? "
               "[c=come back later/e=end now and get the report] ", ("c", "e"))
