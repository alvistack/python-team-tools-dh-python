#!/usr/bin/perl

use strict;
use warnings;
use File::Basename;
use File::Spec;

use Test::Simple tests => 10;

if (-d File::Spec->catdir(dirname(__FILE__), '..', 'dh')) {
    # Test against local checkout
    use lib File::Spec->catdir(dirname(__FILE__), '..', 'dh');
    require 'pybuild.pm';
} else {
    # Test against installed system module package
    require Debian::Debhelper::Buildsystem::pybuild;
}

# Convenience alias to avoid long package names
*make_pep440_compliant = \&Debian::Debhelper::Buildsystem::pybuild::make_pep440_compliant;

# Debian version tests
ok(make_pep440_compliant('1.2') eq '1.2', 'already correct version');
ok(make_pep440_compliant('0.21~bpo9+1') eq '0.21+bpo9.1', 'Debian backport version');
ok(make_pep440_compliant('2.21.3+deb11u1') eq '2.21.3+deb11u1', 'Debian stable update');
ok(make_pep440_compliant('2.21.3+deb11u1~bpo10+1') eq '2.21.3+deb11u1.bpo10.1', 'Debian stable backport');
ok(make_pep440_compliant('0.175~18.04.3') eq '0.175+18.04.3', 'Tilde in Debian version');
ok(make_pep440_compliant('0.1.0-67-g8497b634') eq '0.1.0+67.g8497b634', 'Dash in upstream version');

# Ubuntu version tests
ok(make_pep440_compliant('1.1ubuntu1') eq '1.1+ubuntu1', 'Ubuntu version');
ok(make_pep440_compliant('1.1.4build1') eq '1.1.4+build1', 'Ubuntu no change rebuild');
ok(make_pep440_compliant('2.22.1ubuntu1~bpo20.04.1') eq '2.22.1+ubuntu1.bpo20.04.1', 'Ubuntu backport version');
ok(make_pep440_compliant('2.17.12ubuntu1.1') eq '2.17.12+ubuntu1.1', 'Ubuntu security update');
