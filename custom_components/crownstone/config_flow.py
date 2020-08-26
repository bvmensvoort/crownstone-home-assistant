"""Flow handler for Crownstone."""
import logging
from typing import Optional

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import CONF_SPHERE, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class CrownstoneConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crownstone."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the flow."""
        self.cloud: Optional[CrownstoneCloud] = None
        self.login_info = None
        self.spheres = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
                ),
            )

        self.cloud = CrownstoneCloud(
            email=user_input[CONF_EMAIL],
            password=user_input[CONF_PASSWORD],
            websession=aiohttp_client.async_get_clientsession(self.hass),
        )

        # handle login errors on setup form
        try:
            await self.cloud.async_login()
            # save email and password for later use
            self.login_info = user_input
            # start next flow
            return await self.async_step_sphere()
        except CrownstoneAuthenticationError as auth_error:
            if auth_error.type == "LOGIN_FAILED":
                errors["base"] = "invalid_auth"
            if auth_error.type == "LOGIN_FAILED_EMAIL_NOT_VERIFIED":
                errors["base"] = "account_not_verified"
            if auth_error.type == "USERNAME_EMAIL_REQUIRED":
                errors["base"] = "auth_input_none"
        except CrownstoneUnknownError:
            errors["base"] = "unknown_error"

        # show form again, with the error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_sphere(self, user_input=None):
        """Handle the step for selecting a sphere."""
        # get the spheres for the user
        await self.cloud.spheres.async_update_sphere_data()

        # only 1 sphere configured, don't show form and set this as sphere
        if len(self.cloud.spheres.spheres) == 1:
            user_input = {
                CONF_SPHERE: next(iter(self.cloud.spheres.spheres.values())).name
            }

        # show form with drop down menu
        if user_input is None:
            # generate sphere list
            for sphere in self.cloud.spheres:
                self.spheres.append(sphere.name)

            return self.async_show_form(
                step_id="sphere",
                data_schema=vol.Schema({CONF_SPHERE: vol.In(self.spheres)}),
            )

        # set the unique id
        await self.async_set_unique_id(user_input[CONF_SPHERE])
        # make sure this sphere is only set up once
        self._abort_if_unique_id_configured()

        # cleanup RequestHandler
        self.cloud.reset()

        # return data to main
        return self.async_create_entry(
            title=self.unique_id,
            data={
                CONF_ID: self.unique_id,
                CONF_EMAIL: self.login_info[CONF_EMAIL],
                CONF_PASSWORD: self.login_info[CONF_PASSWORD],
                CONF_SPHERE: user_input[CONF_SPHERE],
            },
        )
