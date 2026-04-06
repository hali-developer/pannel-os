<?php
/**
 * Custom phpMyAdmin Config designed for VPS Panel Database Isolation
 */
declare(strict_types=1);

// Generate a unique secret for cookie-based auth
$cfg['blowfish_secret'] = 'vps-panel-secret-xxxxxxxxxxxxxxxx'; 

$i = 0;
$i++;
$cfg['Servers'][$i]['auth_type'] = 'cookie'; // Standard native login
$cfg['Servers'][$i]['host'] = 'localhost';
$cfg['Servers'][$i]['compress'] = false;
$cfg['Servers'][$i]['AllowNoPassword'] = false;

/**
 * SECURITY ISOLATION CACHE
 * We strictly define which databases cannot be viewed, even if 
 * wildcard grants slipped through contextually. Users are restricted to 
 * their db_name.* internally by MySQL but this adds a safety net.
 */
$cfg['Servers'][$i]['hide_db'] = '^(information_schema|performance_schema|mysql|phpmyadmin|sys|panel_db)$';

/**
 * UI Enhancements for modern visual flow
 */
$cfg['ThemeDefault'] = 'bootstrap'; // Or custom minimal theme
$cfg['NavigationTreeEnableGrouping'] = true;
$cfg['ShowServerInfo'] = false; 
?>
