# k6 summary

scenario: outline

- http_req_connecting: max=0.082, p(90)=0.000, p(95)=0.004, p(99)=0.066, avg=0.004, min=0.000, med=0.000
- http_req_failed: rate=0.000
- http_req_sending: min=0.032, med=0.042, max=0.066, p(90)=0.058, p(95)=0.059, p(99)=0.065, avg=0.044
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.776
- http_req_blocked: max=0.116, p(90)=0.014, p(95)=0.022, p(99)=0.097, avg=0.017, min=0.008, med=0.011
- http_req_receiving: p(90)=0.172, p(95)=0.191, p(99)=0.202, avg=0.121, min=0.033, med=0.134, max=0.204
- http_req_waiting: avg=8.097, min=2.393, med=8.709, max=10.047, p(90)=9.933, p(95)=9.952, p(99)=10.028
- http_req_duration: p(90)=10.098, p(95)=10.197, p(99)=10.218, avg=8.262, min=2.479, med=8.890, max=10.223
- http_req_duration{expected_response:true}: avg=8.262, min=2.479, med=8.890, max=10.223, p(90)=10.098, p(95)=10.197, p(99)=10.218
