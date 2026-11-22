# k6 summary

scenario: course_visits

- http_req_duration: avg=7.342, min=2.669, med=7.200, max=10.083, p(90)=9.449, p(95)=9.743, p(99)=10.015
- http_req_receiving: p(99)=0.245, avg=0.111, min=0.028, med=0.110, max=0.248, p(90)=0.190, p(95)=0.229
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=1.000, max=1.000
- http_req_waiting: min=2.605, med=7.051, max=9.890, p(90)=9.147, p(95)=9.556, p(99)=9.823, avg=7.189
- http_req_sending: p(99)=0.080, avg=0.042, min=0.015, med=0.043, max=0.086, p(90)=0.052, p(95)=0.056
- http_req_blocked: avg=0.016, min=0.004, med=0.011, max=0.109, p(90)=0.017, p(95)=0.028, p(99)=0.093
- http_req_connecting: p(90)=0.000, p(95)=0.004, p(99)=0.064, avg=0.004, min=0.000, med=0.000, max=0.080
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.797
- http_req_duration{expected_response:true}: p(95)=9.743, p(99)=10.015, avg=7.342, min=2.669, med=7.200, max=10.083, p(90)=9.449
