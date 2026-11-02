$(call PKG_INIT_LIB, 1.6.3)
$(PKG)_LIB_VERSION:=1.9.0
$(PKG)_SOURCE:=$(pkg)-$($(PKG)_VERSION).tar.gz
$(PKG)_HASH:=a9ba089cc2c6d26d266bad492de31cadaeb878dea858e22ae3196091718f284b
$(PKG)_SITE:=http://developer.kde.org/~wheeler/files/src
### WEBSITE:=https://taglib.org/
### CHANGES:=https://github.com/taglib/taglib/releases
### CVSREPO:=https://github.com/taglib/taglib

$(PKG)_CATEGORY_LIBS:=Multimedia##ID3 tag

$(PKG)_BINARY:=$($(PKG)_DIR)/taglib/.libs/libtag.so.$($(PKG)_LIB_VERSION)
$(PKG)_STAGING_BINARY:=$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/lib/libtag.so.$($(PKG)_LIB_VERSION)
$(PKG)_TARGET_BINARY:=$($(PKG)_TARGET_DIR)/libtag.so.$($(PKG)_LIB_VERSION)

$(PKG)_DEPENDS_ON += config-host
$(PKG)_DEPENDS_ON += $(STDCXXLIB) zlib
$(PKG)_REBUILD_SUBOPTS += FREETZ_STDCXXLIB

$(PKG)_CONFIGURE_PRE_CMDS += $(call PKG_UPDATE_CONFIGS,./admin/)
# touch some autotools' files to prevent configure from being regenerated
$(PKG)_CONFIGURE_PRE_CMDS += touch -t 200001010000.00 configure.in.in configure.in subdirs acinclude.m4 aclocal.m4 admin/acinclude.m4.in admin/libtool.m4.in;

$(PKG)_CONFIGURE_ENV += lt_cv_deplibs_check_method=pass_all

$(PKG)_CONFIGURE_OPTIONS += --enable-shared
$(PKG)_CONFIGURE_OPTIONS += --enable-static
$(PKG)_CONFIGURE_OPTIONS += --disable-debug
$(PKG)_CONFIGURE_OPTIONS += CXXFLAGS="$(TARGET_CXXFLAGS) -fPIC"


$(PKG_SOURCE_DOWNLOAD)
$(PKG_UNPACKED)
$(PKG_CONFIGURED_CONFIGURE)

$($(PKG)_BINARY): $($(PKG)_DIR)/.configured
	$(SUBMAKE) -C $(TAGLIB_DIR)

$($(PKG)_STAGING_BINARY): $($(PKG)_BINARY)
	$(SUBMAKE) -C $(TAGLIB_DIR) \
		DESTDIR="$(TARGET_TOOLCHAIN_STAGING_DIR)" \
		install
	$(PKG_FIX_LIBTOOL_LA) \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/lib/libtag*.la \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/lib/pkgconfig/taglib*.pc \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/bin/taglib-config

$($(PKG)_TARGET_BINARY): $($(PKG)_STAGING_BINARY)
	$(INSTALL_LIBRARY_STRIP)

$(pkg): $($(PKG)_STAGING_BINARY)

$(pkg)-precompiled: $($(PKG)_TARGET_BINARY)


$(pkg)-clean:
	-$(SUBMAKE) -C $(TAGLIB_DIR) clean
	$(RM) -r \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/include/taglib \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/lib/libtag* \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/lib/pkgconfig/taglib*.pc \
		$(TARGET_TOOLCHAIN_STAGING_DIR)/usr/bin/taglib-config

$(pkg)-uninstall:
	$(RM) $(TAGLIB_TARGET_DIR)/libtag*.so*

$(PKG_FINISH)
