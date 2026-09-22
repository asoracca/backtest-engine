"""Run the fully offline, versioned synthetic demonstration."""

from engine.demo import demo_backtest, render_demo

if __name__ == "__main__":
    print(render_demo(demo_backtest().run()), end="")
