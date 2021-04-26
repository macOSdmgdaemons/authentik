package ldap

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/cookiejar"
	"strings"

	goldap "github.com/go-ldap/ldap/v3"
	httptransport "github.com/go-openapi/runtime/client"
	"github.com/nmcclain/ldap"
	"goauthentik.io/outpost/pkg/client/core"
	"goauthentik.io/outpost/pkg/client/flows"
)

type UIDResponse struct {
	UIDFIeld string `json:"uid_field"`
}

type PasswordResponse struct {
	Password string `json:"password"`
}

func (pi *ProviderInstance) getUsername(dn string) (string, error) {
	if !strings.HasSuffix(dn, pi.BaseDN) {
		return "", errors.New("invalid base DN")
	}
	dns, err := goldap.ParseDN(dn)
	if err != nil {
		return "", err
	}
	for _, part := range dns.RDNs {
		for _, attribute := range part.Attributes {
			if attribute.Type == "DN" {
				return attribute.Value, nil
			}
		}
	}
	return "", errors.New("failed to find dn")
}

func (pi *ProviderInstance) Bind(username string, bindPW string, conn net.Conn) (ldap.LDAPResultCode, error) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		pi.log.WithError(err).Warning("Failed to create cookiejar")
		return ldap.LDAPResultOperationsError, nil
	}
	client := &http.Client{
		Jar: jar,
	}
	passed, err := pi.solveFlowChallenge(username, bindPW, client)
	if err != nil {
		pi.log.WithField("dn", username).WithError(err).Warning("failed to solve challenge")
		return ldap.LDAPResultOperationsError, nil
	}
	if !passed {
		return ldap.LDAPResultInvalidCredentials, nil
	}
	_, err = pi.s.ac.Client.Core.CoreApplicationsCheckAccess(&core.CoreApplicationsCheckAccessParams{
		Slug:       pi.appSlug,
		Context:    context.Background(),
		HTTPClient: client,
	}, httptransport.PassThroughAuth)
	if err != nil {
		if _, denied := err.(*core.CoreApplicationsCheckAccessForbidden); denied {
			pi.log.WithField("dn", username).Info("Access denied for user")
			return ldap.LDAPResultInsufficientAccessRights, nil
		}
		pi.log.WithField("dn", username).WithError(err).Warning("failed to check access")
		return ldap.LDAPResultOperationsError, nil
	}
	pi.log.WithField("dn", username).Info("User has access")
	return ldap.LDAPResultSuccess, nil
}

func (pi *ProviderInstance) solveFlowChallenge(bindDN string, password string, client *http.Client) (bool, error) {
	challenge, err := pi.s.ac.Client.Flows.FlowsExecutorGet(&flows.FlowsExecutorGetParams{
		FlowSlug:   pi.flowSlug,
		Query:      "ldap=true",
		Context:    context.Background(),
		HTTPClient: client,
	}, httptransport.PassThroughAuth)
	if err != nil {
		pi.log.WithError(err).Warning("Failed to get challenge")
		return false, err
	}
	pi.log.WithField("component", challenge.Payload.Component).WithField("type", *challenge.Payload.Type).Debug("Got challenge")
	responseParams := &flows.FlowsExecutorSolveParams{
		FlowSlug:   pi.flowSlug,
		Query:      "ldap=true",
		Context:    context.Background(),
		HTTPClient: client,
	}
	switch challenge.Payload.Component {
	case "ak-stage-identification":
		responseParams.Data = &UIDResponse{UIDFIeld: bindDN}
	case "ak-stage-password":
		responseParams.Data = &PasswordResponse{Password: password}
	default:
		return false, fmt.Errorf("unsupported challenge type: %s", challenge.Payload.Component)
	}
	response, err := pi.s.ac.Client.Flows.FlowsExecutorSolve(responseParams, httptransport.PassThroughAuth)
	pi.log.WithField("component", response.Payload.Component).WithField("type", *response.Payload.Type).Debug("Got response")
	if *response.Payload.Type == "redirect" {
		return true, nil
	}
	if err != nil {
		pi.log.WithError(err).Warning("Failed to submit challenge")
		return false, err
	}
	if len(response.Payload.ResponseErrors) > 0 {
		for key, errs := range response.Payload.ResponseErrors {
			for _, err := range errs {
				pi.log.WithField("key", key).WithField("code", *err.Code).Debug(*err.String)
				return false, nil
			}
		}
	}
	return pi.solveFlowChallenge(bindDN, password, client)
}
