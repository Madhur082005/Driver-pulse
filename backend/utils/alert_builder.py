def build_alert(status, delta=None, expected=None):

    if status == "ahead":
        return "Great pace! You're ahead of target."

    if status == "at_risk":
        # If we know how far behind the driver is, tune the tone.
        if delta is not None and expected is not None and expected > 0:
            frac = abs(delta) / expected

            if frac < 0.10:
                return (
                    "You're slightly behind pace. A couple of good trips can catch you up."
                )

            return (
                "You're significantly behind pace. Consider moving to a high-demand area."
            )

        return "You're behind pace. Move to a high-demand area."

    return "You're on track. Keep going."