import logging
from typing import List, Dict, Any
from datetime import datetime, date
import QuantLib as ql
import numpy as np

# create logger
log = logging.getLogger("CellarLogger")


class OptionsPricingCalculator:
    """
    Options pricing calculator using QuantLib Black-Scholes model.
    Calculates theoretical option prices and Greeks for given parameters.
    """

    def __init__(self):
        log.info("Initializing OptionsPricingCalculator")

    def calculate_option_price(
        self,
        spot_price: float,
        strike_price: float,
        risk_free_rate: float,
        volatility: float,
        expiration_date: date,
        calculation_date: date,
        option_type: str = "call",  # "call" or "put"
        dividend_yield: float = 0.0,
    ) -> Dict[str, float]:
        """
        Calculate option price and Greeks using Black-Scholes model.

        Args:
            spot_price: Current stock price
            strike_price: Strike price of the option
            risk_free_rate: Risk-free interest rate (annual)
            volatility: Implied volatility (annual)
            expiration_date: Option expiration date
            calculation_date: Date for calculation
            option_type: "call" or "put"
            dividend_yield: Continuous dividend yield (annual)

        Returns:
            Dictionary with price and Greeks (delta, gamma, vega, theta, rho)
        """
        try:
            # Convert dates to QuantLib dates
            calc_date_ql = ql.Date(
                calculation_date.day,
                calculation_date.month,
                calculation_date.year,
            )
            exp_date_ql = ql.Date(
                expiration_date.day,
                expiration_date.month,
                expiration_date.year,
            )

            # Set evaluation date
            ql.Settings.instance().evaluationDate = calc_date_ql

            # Setup the option
            option_type_ql = (
                ql.Option.Call if option_type.lower() == "call" else ql.Option.Put
            )
            payoff = ql.PlainVanillaPayoff(option_type_ql, strike_price)
            exercise = ql.EuropeanExercise(exp_date_ql)
            european_option = ql.VanillaOption(payoff, exercise)

            # Market data
            spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot_price))
            flat_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(calc_date_ql, risk_free_rate, ql.Actual365Fixed())
            )
            dividend_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(calc_date_ql, dividend_yield, ql.Actual365Fixed())
            )
            flat_vol_ts = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(
                    calc_date_ql, ql.NullCalendar(), volatility, ql.Actual365Fixed()
                )
            )

            # Black-Scholes process
            bs_process = ql.BlackScholesMertonProcess(
                spot_handle, dividend_ts, flat_ts, flat_vol_ts
            )

            # Pricing engine
            european_option.setPricingEngine(
                ql.AnalyticEuropeanEngine(bs_process)
            )

            # Calculate price and Greeks
            result = {
                "price": european_option.NPV(),
                "delta": european_option.delta(),
                "gamma": european_option.gamma(),
                "vega": european_option.vega() / 100,  # Convert to % volatility change
                "theta": european_option.theta() / 365,  # Daily theta
                "rho": european_option.rho() / 100,  # Convert to % rate change
            }

            return result

        except Exception as e:
            log.error(f"Error calculating option price: {e}")
            return {
                "price": 0.0,
                "delta": 0.0,
                "gamma": 0.0,
                "vega": 0.0,
                "theta": 0.0,
                "rho": 0.0,
            }

    def calculate_options_chain(
        self,
        spot_price: float,
        strike_prices: List[float],
        risk_free_rate: float,
        volatility: float,
        expiration_date: date,
        calculation_date: date = None,
        dividend_yield: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Calculate options chain for multiple strike prices.

        Args:
            spot_price: Current stock price
            strike_prices: List of strike prices
            risk_free_rate: Risk-free interest rate
            volatility: Implied volatility
            expiration_date: Option expiration date
            calculation_date: Date for calculation (defaults to today)
            dividend_yield: Continuous dividend yield

        Returns:
            List of dictionaries with strike price and both call/put data
        """
        if calculation_date is None:
            calculation_date = date.today()

        chain = []
        for strike in strike_prices:
            call_data = self.calculate_option_price(
                spot_price=spot_price,
                strike_price=strike,
                risk_free_rate=risk_free_rate,
                volatility=volatility,
                expiration_date=expiration_date,
                calculation_date=calculation_date,
                option_type="call",
                dividend_yield=dividend_yield,
            )

            put_data = self.calculate_option_price(
                spot_price=spot_price,
                strike_price=strike,
                risk_free_rate=risk_free_rate,
                volatility=volatility,
                expiration_date=expiration_date,
                calculation_date=calculation_date,
                option_type="put",
                dividend_yield=dividend_yield,
            )

            chain.append(
                {
                    "strike": strike,
                    "call": call_data,
                    "put": put_data,
                    "is_atm": abs(strike - spot_price) < (spot_price * 0.01),  # Within 1%
                }
            )

        return chain

    def generate_strike_prices(
        self, spot_price: float, num_strikes: int = 11, strike_interval_pct: float = 2.5
    ) -> List[float]:
        """
        Generate a list of strike prices centered around the spot price.

        Args:
            spot_price: Current stock price
            num_strikes: Number of strikes to generate (should be odd for symmetry)
            strike_interval_pct: Percentage interval between strikes

        Returns:
            List of strike prices
        """
        strikes = []
        mid_point = num_strikes // 2

        for i in range(num_strikes):
            offset = (i - mid_point) * strike_interval_pct
            strike = spot_price * (1 + offset / 100)
            # Round to nearest 0.5 or 1.0 depending on price level
            if strike < 50:
                strike = round(strike * 2) / 2  # Round to nearest 0.5
            elif strike < 200:
                strike = round(strike)  # Round to nearest 1
            else:
                strike = round(strike / 5) * 5  # Round to nearest 5

            strikes.append(strike)

        return sorted(strikes)
