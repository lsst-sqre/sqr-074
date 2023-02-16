:tocdepth: 1

Abstract
========

The purpose of Phalanx_ has expanded from its original role in managing the configuration for the Rubin Science Platform to providing an installation and configuration platform for services deployed on Kubernetes clusters, which may contain any number of Rubin Science Platform services or none.
New, minimal installations need validation to ensure that basic services are running correctly, including mechanisms to both manually and automatically test. Feedback that an installation has worked (or how it may be failing) is particularly useful for deployers without previous experience with phalanx, and is an important element towards productizing the platform for further community use. 
This tech note proposes a new validation service plus supporting infrastructure for automated testing.

.. _Phalanx: https://phalanx.lsst.io/

Problem statement
=================

Current state
-------------

Currently, the primary testing mechanism for a Phalanx deployment is mobu_, a framework for periodically running Python tests and reporting any failures to Slack.
mobu currently supports running notebooks via the Notebook Aspect or running TAP queries directly against an IVOA TAP service.
Other components are tested by writing notebooks that exercise them (usually via the system-test_ repository), and then running those notebooks with mobu.

.. _mobu: https://github.com/lsst-sqre/mobu
.. _system-test: https://github.com/lsst-sqre/system-test

While mobu can easily be generalized to run other checks, it is designed to exercise services within the same Kubernetes deployment.
In a Phalanx deployment not intended for use as a Science Platform, none of the services mobu knows how to exercise may exist.
Currently, there is no separate service designed specifically for exercising basic Phalanx functionality that is appropriate to deploy in Phalanx environments that are not intended to run Science Platform services.

Desired state
-------------

Phalanx should have a well-defined minimal functionality, independent of any services (including Science Platform services) deployed on top of it, and a corresponding well-defined group of minimal services that are mandatory on any Phalanx deployment.
As part of that minimal set, add a new web service, Muster [#]_, which provides web pages that verify basic deployment functionality.

.. [#] A "phalanx" is a military formation, and one musters a military unit to account for all of its members and ensure they are present.
       A Phalanx deployment in which all Muster web pages report success would then "pass Muster."

Then, add a new action to the Phalanx installer that verifies the new installation.
This would use Argo CD to ensure that all configured applications are healthy, and would use Muster to verify that basic functionality was working.
Add this new verification to the Phalanx CI action that uses minikube to check for obvious regressions.

Minimal services
================

Based on experience deploying the new Roundtable cluster, a proposed starting point for minimum Phalanx services is an ingress controller provided by NGINX, certificate management, Vault integration for secrets, authentication and authorization, and a home page.
This corresponds to the ``cert-manager``, ``gafaelfawr``, ``ingress-nginx``, ``squareone``, and ``vault-secrets-operator`` services.

Currently, we also always deploy an in-cluster PostgreSQL server, but in the longer term we hope to eliminate that in favor of a requirement that the deployment environment provide PostgreSQL as a service.

Most of the default Gafaelfawr scopes are only meaningful for a Science Platform deployment.
A possible minimal set of scopes would be the ``admin:token`` and ``user:token`` scopes used internally by Gafaelfawr, plus ``exec:admin`` for general administrative access.
(We will probably rename ``exec:admin`` to ``admin:<something>`` at some point in the future for consistency.)

Muster
======

The new Muster service would be a FastAPI_ web service using Safir_.
The initial set of routes it would support are:

.. _FastAPI: https://fastapi.tiangolo.com/
.. _Safir: https://safir.lsst.io/

#. An unauthenticated route serving a static success page.

#. An authenticated route that requires the ``exec:admin`` scope but does not request any delegated tokens.
   The resulting web page should report all of the metadata about the user that is released by Gafaelfawr in HTTP headers, and also verify that the ``Cookie`` and ``Authorization`` headers are being stripped correctly.

#. An authenticated route that requires the ``exec:admin`` scope and requests a delegated token with no scopes.
   Muster should then query Gafaelfawr with the delegated token and report all of the user information available to Gafaelfawr, as well as check that it matches the information released in the HTTP headers.
   This will test LDAP integration, UID and GID assignment, and other optional features of Gafaelfawr if they are enabled.

All of the Muster ingresses should be defined as a GafaelfawrIngress_, so this will also test the Gafaelfawr Kubernetes operator.
Gafaelfawr itself requires PostgreSQL and Vault secrets management, so this will exercise those services, as well as certificate management and ingress configuration to reach the service in the first place and correctly invoke Gafaelfawr.

.. _GafaelfawrIngress: https://gafaelfawr.lsst.io/user-guide/gafaelfawringress.html

There should be two versions of each of these routes, one that returns HTML for use by humans and one that returns JSON for use by automated tests (see :ref:`automated-testing`).

.. _automated-testing:

Automated testing
=================

Use cases
---------

In addition to allowing human verification of the basic functionality of a new deployment, we also want to support automated testing.
This will come in two forms:

- Optionally run a validation test of a newly-deployed cluster immediately after deploying it.
  This would be done in conjunction with asking Argo CD if health checks are passing for all applications and would be done in the installer.
  The CI minikube deployment would run this check.

- Regularly run the same validation tests for existing clusters so that we know if any of the basic functionality breaks.
  This is well-suited for mobu, which already runs similar checks for existing clusters.

Proposed implementation
-----------------------

The JSON routes of Muster should, in addition to summarizing all of the checks run and any errors, provide a top-level pass-fail status.
We can then write a Muster client that does the following:

#. Obtain the Gafaelfawr bootstrap token from the Gafaelfawr secret.
#. Using that token, create a token for a ``bot-check-muster`` user with ``exec:admin`` scope.
#. Query all of the Muster JSON endpoints, providing that token to the ones requiring authentication, and check that the top-level status is pass.
#. Query a Muster endpoint that requires authentication without providing the token and check that a 401 status is returned.
#. Create a token for ``bot-check-muster`` without any scopes, and query one of the Muster endpoints that requires authentication.
   Check the return status and the correctness of the headers.
#. Pass an invalid token to the same endpoint and check the return status and correctness of the headers and response body.

The last two steps test the special Gafaelfawr integration with ingress-nginx to pass additional headers and a correct return status and response body when an auth subrequest handler fails.

For ongoing testing, we want mobu to run the same code periodically.

To avoid duplicating the same code in multiple places, we can add this code to mobu as a new ``MusterRunner`` class.
Then, add a new endpoint to mobu that, rather than starting a continuous runner, executes a runner once and returns its results directly as the response of that endpoint.
Validation testing can then be done by deploying mobu without any configured monkeys (test runners), and then invoking that endpoint to run the ``MusterRunner``.
(The drawback of this approach is that it adds mobu to the minimum application set for a Phalanx deployment, but that seems better than duplicating this code or creating a new special-purpose library package that will require ongoing maintenance.)

The overall architecture would then look like the following:

.. figure:: /_static/architecture.png
   :name: Phalanx validation architecture

   The ingress is shown via annotated edges rather than as a separate Kubernetes service for clarity, since the services talk to each other via the ingress.
