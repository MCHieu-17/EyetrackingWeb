# k6 summary

scenario: outline

- vus: min=1.000, max=1.000
- http_req_waiting: avg=7.363, min=2.059, med=7.445, max=9.903, p(90)=9.756, p(95)=9.852, p(99)=9.893
- http_req_blocked: avg=0.023, min=0.007, med=0.011, max=0.149, p(90)=0.022, p(95)=0.113, p(99)=0.141
- http_req_duration: p(90)=9.911, p(95)=10.017, p(99)=10.048, avg=7.552, min=2.112, med=7.801, max=10.055
- http_req_failed: rate=0.000
- http_req_sending: p(95)=0.054, p(99)=0.078, avg=0.042, min=0.013, med=0.042, max=0.084, p(90)=0.047
- http_req_connecting: max=0.082, p(90)=0.000, p(95)=0.004, p(99)=0.066, avg=0.004, min=0.000, med=0.000
- http_req_receiving: avg=0.146, min=0.038, med=0.119, max=0.470, p(90)=0.267, p(95)=0.285, p(99)=0.433
- http_req_duration{expected_response:true}: p(95)=10.017, p(99)=10.048, avg=7.552, min=2.112, med=7.801, max=10.055, p(90)=9.911
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- iterations: count=20.000, rate=4.792
