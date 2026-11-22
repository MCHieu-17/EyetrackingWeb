# k6 summary

scenario: samples

- http_req_duration: med=15.397, max=23.811, p(90)=20.508, p(95)=21.063, p(99)=22.284, avg=14.467, min=3.460
- http_req_duration{expected_response:true}: med=15.397, max=23.811, p(90)=20.508, p(95)=21.063, p(99)=22.284, avg=14.467, min=3.460
- http_req_sending: avg=0.040, min=0.005, med=0.040, max=0.169, p(90)=0.052, p(95)=0.058, p(99)=0.078
- iterations: count=233.000, rate=23.102
- http_req_receiving: med=0.095, max=0.483, p(90)=0.214, p(95)=0.253, p(99)=0.326, avg=0.110, min=0.013
- http_req_waiting: med=15.219, max=23.660, p(90)=20.380, p(95)=20.967, p(99)=22.174, avg=14.316, min=3.418
- http_req_blocked: med=0.011, max=0.138, p(90)=0.013, p(95)=0.015, p(99)=0.131, avg=0.013, min=0.002
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_connecting: p(99)=0.100, avg=0.002, min=0.000, med=0.000, max=0.101, p(90)=0.000, p(95)=0.000
