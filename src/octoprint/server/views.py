# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2015 The OctoPrint Project - Released under terms of the AGPLv3 License"

import os

from collections import defaultdict
from flask import request, g, url_for, make_response, render_template, send_from_directory

import octoprint.plugin

from octoprint.server import app, userManager, pluginManager, gettext, debug, LOCALES, VERSION, DISPLAY_VERSION, UI_API_KEY
from octoprint.settings import settings

from . import util

import logging
_logger = logging.getLogger(__name__)


@app.route("/")
@util.flask.cached(refreshif=lambda: util.flask.cache_check_headers() or "_refresh" in request.values, key=lambda: "view/%s/%s" % (request.path, g.locale))
def index():

	#~~ a bunch of settings

	enable_gcodeviewer = settings().getBoolean(["gcodeViewer", "enabled"])
	enable_timelapse = (settings().get(["webcam", "snapshot"]) and settings().get(["webcam", "ffmpeg"]))
	enable_systemmenu = settings().get(["system"]) is not None and settings().get(["system", "actions"]) is not None and len(settings().get(["system", "actions"])) > 0
	enable_accesscontrol = userManager is not None
	preferred_stylesheet = settings().get(["devel", "stylesheet"])
	locales = dict((l.language, dict(language=l.language, display=l.display_name, english=l.english_name)) for l in LOCALES)

	#~~ prepare assets

	supported_stylesheets = ("css", "less")
	assets = dict(
		js=[],
		stylesheets=[]
	)
	assets["js"] = [
		url_for('static', filename='js/app/viewmodels/appearance.js'),
		url_for('static', filename='js/app/viewmodels/connection.js'),
		url_for('static', filename='js/app/viewmodels/control.js'),
		url_for('static', filename='js/app/viewmodels/firstrun.js'),
		url_for('static', filename='js/app/viewmodels/files.js'),
		url_for('static', filename='js/app/viewmodels/loginstate.js'),
		url_for('static', filename='js/app/viewmodels/navigation.js'),
		url_for('static', filename='js/app/viewmodels/printerstate.js'),
		url_for('static', filename='js/app/viewmodels/printerprofiles.js'),
		url_for('static', filename='js/app/viewmodels/settings.js'),
		url_for('static', filename='js/app/viewmodels/slicing.js'),
		url_for('static', filename='js/app/viewmodels/temperature.js'),
		url_for('static', filename='js/app/viewmodels/terminal.js'),
		url_for('static', filename='js/app/viewmodels/users.js'),
		url_for('static', filename='js/app/viewmodels/log.js'),
		url_for('static', filename='js/app/viewmodels/usersettings.js')
	]
	if enable_gcodeviewer:
		assets["js"] += [
			url_for('static', filename='js/app/viewmodels/gcode.js'),
			url_for('static', filename='gcodeviewer/js/ui.js'),
			url_for('static', filename='gcodeviewer/js/gCodeReader.js'),
			url_for('static', filename='gcodeviewer/js/renderer.js')
		]
	if enable_timelapse:
		assets["js"].append(url_for('static', filename='js/app/viewmodels/timelapse.js'))

	if preferred_stylesheet == "less":
		assets["stylesheets"].append(("less", url_for('static', filename='less/octoprint.less')))
	elif preferred_stylesheet == "css":
		assets["stylesheets"].append(("css", url_for('static', filename='css/octoprint.css')))

	asset_plugins = pluginManager.get_implementations(octoprint.plugin.AssetPlugin)
	for implementation in asset_plugins:
		name = implementation._identifier
		all_assets = implementation.get_assets()

		if "js" in all_assets:
			for asset in all_assets["js"]:
				assets["js"].append(url_for('plugin_assets', name=name, filename=asset))

		if preferred_stylesheet in all_assets:
			for asset in all_assets[preferred_stylesheet]:
				assets["stylesheets"].append((preferred_stylesheet, url_for('plugin_assets', name=name, filename=asset)))
		else:
			for stylesheet in supported_stylesheets:
				if not stylesheet in all_assets:
					continue

				for asset in all_assets[stylesheet]:
					assets["stylesheets"].append((stylesheet, url_for('plugin_assets', name=name, filename=asset)))
				break

	##~~ prepare templates

	templates = dict(
		navbar=dict(order=[], entries=dict()),
		sidebar=dict(order=[], entries=dict()),
		tab=dict(order=[], entries=dict()),
		settings=dict(order=[], entries=dict()),
		usersettings=dict(order=[], entries=dict()),
		generic=dict(order=[], entries=dict())
	)
	template_types = templates.keys()

	# navbar

	templates["navbar"]["entries"] = dict(
		settings=dict(template="navbar/settings.jinja2", _div="navbar_settings", styles=["display: none"], data_bind="visible: loginState.isAdmin")
	)
	if enable_accesscontrol:
		templates["navbar"]["entries"]["login"] = dict(template="navbar/login.jinja2", _div="navbar_login", classes=["dropdown"], custom_bindings=False)
	if enable_systemmenu:
		templates["navbar"]["entries"]["systemmenu"] = dict(template="navbar/systemmenu.jinja2", _div="navbar_systemmenu", styles=["display: none"], classes=["dropdown"], data_bind="visible: loginState.isAdmin", custom_bindings=False)

	# sidebar

	templates["sidebar"]["entries"]= dict(
		connection=(gettext("Connection"), dict(template="sidebar/connection.jinja2", _div="connection", icon="signal", styles_wrapper=["display: none"], data_bind="visible: loginState.isAdmin")),
		state=(gettext("State"), dict(template="sidebar/state.jinja2", _div="state", icon="info-sign")),
		files=(gettext("Files"), dict(template="sidebar/files.jinja2", _div="files", icon="list", classes_content=["overflow_visible"], template_header="sidebar/files_header.jinja2"))
	)

	# tabs

	templates["tab"]["entries"] = dict(
		temperature=(gettext("Temperature"), dict(template="tabs/temperature.jinja2", _div="temp")),
		control=(gettext("Control"), dict(template="tabs/control.jinja2", _div="control")),
		terminal=(gettext("Terminal"), dict(template="tabs/terminal.jinja2", _div="term")),
	)
	if enable_gcodeviewer:
		templates["tab"]["entries"]["gcodeviewer"] = (gettext("GCode Viewer"), dict(template="tabs/gcodeviewer.jinja2", _div="gcode"))
	if enable_timelapse:
		templates["tab"]["entries"]["timelapse"] = (gettext("Timelapse"), dict(template="tabs/timelapse.jinja2", _div="timelapse"))

	# settings dialog

	templates["settings"]["entries"] = dict(
		section_printer=(gettext("Printer"), None),

		serial=(gettext("Serial Connection"), dict(template="dialogs/settings/serialconnection.jinja2", _div="settings_serialConnection", custom_bindings=False)),
		printerprofiles=(gettext("Printer Profiles"), dict(template="dialogs/settings/printerprofiles.jinja2", _div="settings_printerProfiles", custom_bindings=False)),
		temperatures=(gettext("Temperatures"), dict(template="dialogs/settings/temperatures.jinja2", _div="settings_temperature", custom_bindings=False)),
		terminalfilters=(gettext("Terminal Filters"), dict(template="dialogs/settings/terminalfilters.jinja2", _div="settings_terminalFilters", custom_bindings=False)),
		gcodescripts=(gettext("GCODE Scripts"), dict(template="dialogs/settings/gcodescripts.jinja2", _div="settings_gcodeScripts", custom_bindings=False)),

		section_features=(gettext("Features"), None),

		features=(gettext("Features"), dict(template="dialogs/settings/features.jinja2", _div="settings_features", custom_bindings=False)),
		webcam=(gettext("Webcam"), dict(template="dialogs/settings/webcam.jinja2", _div="settings_webcam", custom_bindings=False)),
		api=(gettext("API"), dict(template="dialogs/settings/api.jinja2", _div="settings_api", custom_bindings=False)),

		section_octoprint=(gettext("OctoPrint"), None),

		folders=(gettext("Folders"), dict(template="dialogs/settings/folders.jinja2", _div="settings_folders", custom_bindings=False)),
		appearance=(gettext("Appearance"), dict(template="dialogs/settings/appearance.jinja2", _div="settings_appearance", custom_bindings=False)),
		logs=(gettext("Logs"), dict(template="dialogs/settings/logs.jinja2", _div="settings_logs")),
	)
	if enable_accesscontrol:
		templates["settings"]["entries"]["accesscontrol"] = (gettext("Access Control"), dict(template="dialogs/settings/accesscontrol.jinja2", _div="settings_users", custom_bindings=False))

	# user settings dialog

	if enable_accesscontrol:
		templates["usersettings"]["entries"] = dict(
			access=(gettext("Access"), dict(template="dialogs/usersettings/access.jinja2", _div="usersettings_access", custom_bindings=False)),
			interface=(gettext("Interface"), dict(template="dialogs/usersettings/interface.jinja2", _div="usersettings_interface", custom_bindings=False)),
		)

	# extract data from template plugins

	template_plugins = pluginManager.get_implementations(octoprint.plugin.TemplatePlugin)

	# rules for transforming template configs to template entries
	rules = dict(
		navbar=dict(div=lambda x: "navbar_plugin_" + x, template=lambda x: x + "_navbar.jinja2", to_entry=lambda data: data),
		sidebar=dict(div=lambda x: "sidebar_plugin_" + x, template=lambda x: x + "_sidebar.jinja2", to_entry=lambda data: (data["name"], data)),
		tab=dict(div=lambda x: "tab_plugin_" + x, template=lambda x: x + "_tab.jinja2", to_entry=lambda data: (data["name"], data)),
		settings=dict(div=lambda x: "settings_plugin_" + x, template=lambda x: x + "_settings.jinja2", to_entry=lambda data: (data["name"], data)),
		usersettings=dict(div=lambda x: "usersettings_plugin_" + x, template=lambda x: x + "_usersettings.jinja2", to_entry=lambda data: (data["name"], data)),
		generic=dict(template=lambda x: x + ".jinja2", to_entry=lambda data: data)
	)

	plugin_vars = dict()
	plugin_names = set()
	for implementation in template_plugins:
		name = implementation._identifier
		plugin_names.add(name)

		vars = implementation.get_template_vars()
		if not isinstance(vars, dict):
			vars = dict()

		for var_name, var_value in vars.items():
			plugin_vars["plugin_" + name + "_" + var_name] = var_value

		configs = implementation.get_template_configs()
		if not isinstance(configs, (list, tuple)):
			configs = []

		includes = _process_template_configs(name, implementation, configs, rules)

		for t in template_types:
			for include in includes[t]:
				if t == "navbar" or t == "generic":
					data = include
				else:
					data = include[1]

				key = data["_key"]
				if "replaces" in data:
					key = data["replaces"]
				templates[t]["entries"][key] = include

	#~~ order internal templates and plugins

	# make sure that
	# 1) we only have keys in our ordered list that we have entries for and
	# 2) we have all entries located somewhere within the order

	for t in template_types:
		default_order = settings().get(["appearance", "components", "order", t], merged=True, config=dict())
		configured_order = settings().get(["appearance", "components", "order", t], merged=True)
		configured_disabled = settings().get(["appearance", "components", "disabled", t])

		# first create the ordered list of all component ids according to the configured order
		templates[t]["order"] = [x for x in configured_order if x in templates[t]["entries"] and not x in configured_disabled]

		# now append the entries from the default order that are not already in there
		templates[t]["order"] += [x for x in default_order if not x in templates[t]["order"] and x in templates[t]["entries"] and not x in configured_disabled]

		all_ordered = set(templates[t]["order"])
		all_disabled = set(configured_disabled)

		# check if anything is missing, if not we are done here
		missing_in_order = set(templates[t]["entries"].keys()).difference(all_ordered).difference(all_disabled)
		if len(missing_in_order) == 0:
			continue

		# finally add anything that's not included in our order yet
		sorted_missing = list(missing_in_order)
		if not t == "navbar" and not t == "generic":
			# anything but navbar and generic components get sorted by their name
			sorted_missing = sorted(missing_in_order, key=lambda x: templates[t]["entries"][x][0])

		if t == "navbar":
			# additional navbar components are prepended
			templates[t]["order"] = sorted_missing + templates[t]["order"]
		elif t == "sidebar" or t == "tab" or t == "generic" or t == "usersettings":
			# additional sidebar, generic or usersettings components are appended
			templates[t]["order"] += sorted_missing
		elif t == "settings":
			# additional settings items are added to the plugin section
			templates[t]["entries"]["section_plugins"] = (gettext("Plugins"), None)
			templates[t]["order"] += ["section_plugins"] + sorted_missing

	#~~ prepare full set of template vars for rendering

	render_kwargs = dict(
		webcamStream=settings().get(["webcam", "stream"]),
		enableTemperatureGraph=settings().get(["feature", "temperatureGraph"]),
		enableAccessControl=userManager is not None,
		enableSdSupport=settings().get(["feature", "sdSupport"]),
		firstRun=settings().getBoolean(["server", "firstRun"]) and (userManager is None or not userManager.hasBeenCustomized()),
		debug=debug,
		version=VERSION,
		display_version=DISPLAY_VERSION,
		gcodeMobileThreshold=settings().get(["gcodeViewer", "mobileSizeThreshold"]),
		gcodeThreshold=settings().get(["gcodeViewer", "sizeThreshold"]),
		uiApiKey=UI_API_KEY,
		templates=templates,
		assets=assets,
		pluginNames=plugin_names,
		locales=locales
	)
	render_kwargs.update(plugin_vars)

	#~~ render!

	return render_template(
		"index.jinja2",
		**render_kwargs
	)


def _process_template_configs(name, implementation, configs, rules):
	from jinja2.exceptions import TemplateNotFound

	counters = dict(
		navbar=1,
		sidebar=1,
		tab=1,
		settings=1,
		generic=1
	)
	includes = defaultdict(list)

	for config in configs:
		if not isinstance(config, dict):
			continue
		if not "type" in config:
			continue

		template_type = config["type"]
		del config["type"]

		if not template_type in rules:
			continue
		rule = rules[template_type]

		data = _process_template_config(name, implementation, rule, config=config, counter=counters[template_type])
		if data is None:
			continue

		includes[template_type].append(rule["to_entry"](data))
		counters[template_type] += 1

	for template_type in rules:
		if len(includes[template_type]) == 0:
			# if no template of that type was added by the config, we'll try to use the default template name
			rule = rules[template_type]
			data = _process_template_config(name, implementation, rule)
			if data is not None:
				try:
					app.jinja_env.get_or_select_template(data["template"])
				except TemplateNotFound:
					pass
				else:
					includes[template_type].append(rule["to_entry"](data))

	return includes

def _process_template_config(name, implementation, rule, config=None, counter=1):
	if "mandatory" in rule:
		for mandatory in rule["mandatory"]:
			if not mandatory in config:
				return None

	if config is None:
		config = dict()
	data = dict(config)

	if not "suffix" in data and counter > 1:
		data["suffix"] = "_%d" % counter

	if "div" in data:
		data["_div"] = data["div"]
	elif "div" in rule:
		data["_div"] = rule["div"](name)
		if "suffix" in data:
			data["_div"] = data["_div"] + data["suffix"]

	if not "template" in data:
		data["template"] = rule["template"](name)

	if not "name" in data:
		data["name"] = implementation._plugin_name

	if not "custom_bindings" in data or data["custom_bindings"]:
		data_bind = "allowBindings: true"
		if "data_bind" in data:
			data_bind = data_bind + ", " + data["data_bind"]
		data["data_bind"] = data_bind

	data["_key"] = "plugin_" + name
	if "suffix" in data:
		data["_key"] += data["suffix"]

	return data

@app.route("/robots.txt")
def robotsTxt():
	return send_from_directory(app.static_folder, "robots.txt")


@app.route("/i18n/<string:locale>/<string:domain>.js")
@util.flask.cached(refreshif=lambda: util.flask.cache_check_headers() or "_refresh" in request.values, key=lambda: "view/%s/%s" % (request.path, g.locale))
def localeJs(locale, domain):
	messages = dict()
	plural_expr = None

	if locale != "en":
		from flask import _request_ctx_stack
		from babel.messages.pofile import read_po

		def messages_from_po(base_path, locale, domain):
			path = os.path.join(base_path, locale)
			if not os.path.isdir(path):
				return None, None

			path = os.path.join(path, "LC_MESSAGES", "{domain}.po".format(**locals()))
			if not os.path.isfile(path):
				return None, None

			messages = dict()
			with file(path) as f:
				catalog = read_po(f, locale=locale, domain=domain)

				for message in catalog:
					message_id = message.id
					if isinstance(message_id, (list, tuple)):
						message_id = message_id[0]
					messages[message_id] = message.string

			return messages, catalog.plural_expr

		user_base_path = os.path.join(settings().getBaseFolder("translations"))
		user_plugin_path = os.path.join(user_base_path, "_plugins")

		# plugin translations
		plugins = octoprint.plugin.plugin_manager().enabled_plugins
		for name, plugin in plugins.items():
			dirs = [os.path.join(user_plugin_path, name), os.path.join(plugin.location, 'translations')]
			for dirname in dirs:
				if not os.path.isdir(dirname):
					continue

				plugin_messages, _ = messages_from_po(dirname, locale, domain)

				if plugin_messages is not None:
					messages = octoprint.util.dict_merge(messages, plugin_messages)
					_logger.debug("Using translation folder {dirname} for locale {locale} of plugin {name}".format(**locals()))
					break
			else:
				_logger.debug("No translations for locale {locale} for plugin {name}".format(**locals()))

		# core translations
		ctx = _request_ctx_stack.top
		base_path = os.path.join(ctx.app.root_path, "translations")

		dirs = [user_base_path, base_path]
		for dirname in dirs:
			core_messages, plural_expr = messages_from_po(dirname, locale, domain)

			if core_messages is not None:
				messages = octoprint.util.dict_merge(messages, core_messages)
				_logger.debug("Using translation folder {dirname} for locale {locale} of core translations".format(**locals()))
				break
		else:
			_logger.debug("No core translations for locale {locale}".format(**locals()))

	catalog = dict(
		messages=messages,
		plural_expr=plural_expr,
		locale=locale,
		domain=domain
	)

	return render_template("i18n.js.jinja2", catalog=catalog)


@app.route("/plugin_assets/<string:name>/<path:filename>")
def plugin_assets(name, filename):
	asset_plugins = pluginManager.get_filtered_implementations(lambda p: p._identifier == name, octoprint.plugin.AssetPlugin)

	if not asset_plugins:
		return make_response("Asset not found", 404)

	if len(asset_plugins) > 1:
		return make_response("More than one asset provider for {name}, can't proceed".format(name=name), 500)

	asset_plugin = asset_plugins[0]
	asset_folder = asset_plugin.get_asset_folder()
	if asset_folder is None:
		return make_response("Asset not found", 404)

	return send_from_directory(asset_folder, filename)


