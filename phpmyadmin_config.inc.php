<?php
/**
 * phpMyAdmin Configuration for VPS Panel
 * Database isolation: each user only sees their own databases.
 */
declare(strict_types=1);

// Unique blowfish secret (change this in production!)
$cfg['blowfish_secret'] = 'vps-panel-change-this-to-random-32-chars!!';

$i = 0;
$i++;

// Server configuration
$cfg['Servers'][$i]['auth_type'] = 'cookie';
$cfg['Servers'][$i]['host'] = 'localhost';
$cfg['Servers'][$i]['compress'] = false;
$cfg['Servers'][$i]['AllowNoPassword'] = false;

/**
 * SECURITY: Hide system databases from all users.
 * Each client user is already restricted by MySQL GRANT to their own db,
 * but this adds a UI-level safety net.
 */
$cfg['Servers'][$i]['hide_db'] = '^(information_schema|performance_schema|mysql|phpmyadmin|sys|pannel_db)$';

/**
 * UI Settings
 */
$cfg['ThemeDefault'] = 'pmahomme';
$cfg['NavigationTreeEnableGrouping'] = true;
$cfg['ShowServerInfo'] = false;
$cfg['ShowPhpInfo'] = false;
$cfg['ShowCreateDb'] = false;

/**
 * Security Settings
 */
$cfg['LoginCookieValidity'] = 3600;
$cfg['LoginCookieStore'] = 0;
$cfg['LoginCookieDeleteAll'] = true;
?>
