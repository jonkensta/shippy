"""
Postage convenience functions.
"""

import easypost


# pylint: disable=too-few-public-methods
class Builder:
    """Shipment builder"""

    def __init__(self, apikey):
        self._apikey = apikey

    def _address_from_dict(self, dict_):
        """Convert a dict to an address."""
        dict_ = dict(dict_)
        dict_['zip'] = dict_.pop('zipcode')
        dict_['country'] = 'US'
        dict_['phone'] = ''
        return easypost.Address.create_and_verify(
            api_key=self._apikey, **dict_
        )

    def _build_parcel(self, weight):
        """Build easypost Parcel given weight"""
        return easypost.Parcel.create(
            api_key=self._apikey,
            predefined_package='Parcel', weight=weight
        )

    def _build_shipment(self, from_addr, to_addr, weight):
        """Build shipment from easypost addresses and weight"""
        parcel = self._build_parcel(weight)
        options = dict(special_rates_eligibility='USPS.LIBRARYMAIL')
        return easypost.Shipment.create(
            api_key=self._apikey,
            from_address=from_addr, to_address=to_addr,
            parcel=parcel, options=options
        )

    def __call__(self, from_addr, to_addr, weight):
        """Purchase postage of a Parcel with a given weight in ounces."""
        from_addr, to_addr = map(self._address_from_dict, (from_addr, to_addr))
        shipment = self._build_shipment(from_addr, to_addr, weight)
        rate = shipment.lowest_rate(['USPS'])
        shipment.buy(rate=rate)
        return shipment

def extract_data(shipment):
    """Extract useful data from easypost shipment object."""
    return dict(
        postage=int(round(100 * float(shipment.selected_rate.rate))),
        weight=int(shipment.parcel.weight),
        tracking_code=shipment.tracking_code,
        tracking_url=shipment.tracker.public_url,
    )
