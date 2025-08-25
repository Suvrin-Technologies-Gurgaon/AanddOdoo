from odoo import models
import math


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def amount_to_text(self, amount):
        """Method to convert amount to text"""

        def _get_indian_number_word(n):
            ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
            tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
            teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
                     "Sixteen", "Seventeen", "Eighteen", "Nineteen"]

            def two_digit_word(n):
                if n < 10:
                    return ones[n]
                elif 10 <= n < 20:
                    return teens[n - 10]
                else:
                    return tens[n // 10] + (" " + ones[n % 10] if (n % 10) != 0 else "")

            def segment(n, label):
                return (two_digit_word(n) + " " + label + " ") if n else ""

            output = ""
            crore = n // 10000000
            n %= 10000000
            lakh = n // 100000
            n %= 100000
            thousand = n // 1000
            n %= 1000
            hundred = n // 100
            n %= 100
            output += segment(crore, "Crore")
            output += segment(lakh, "Lakh")
            output += segment(thousand, "Thousand")
            output += segment(hundred, "Hundred")
            if n > 0 and output != "":
                output += "and "
            output += two_digit_word(n)
            return output.strip()

        rupees = int(math.floor(amount))
        paise = int(round((amount - rupees) * 100))
        words = "Rupees " + _get_indian_number_word(rupees)
        if paise:
            words += " and Paise " + _get_indian_number_word(paise)
        words += " Only"
        return words
