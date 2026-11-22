# k6 summary

scenario: enrollments

- http_req_waiting: max=5.194, p(90)=5.082, p(95)=5.106, p(99)=5.176, avg=4.520, min=1.613, med=4.647
- http_req_receiving: avg=0.144, min=0.031, med=0.125, max=0.291, p(90)=0.239, p(95)=0.287, p(99)=0.290
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: p(90)=5.261, p(95)=5.291, p(99)=5.329, avg=4.707, min=1.658, med=4.855, max=5.339
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_sending: p(90)=0.056, p(95)=0.058, p(99)=0.061, avg=0.043, min=0.014, med=0.045, max=0.061
- http_req_connecting: p(90)=0.000, p(95)=0.004, p(99)=0.067, avg=0.004, min=0.000, med=0.000, max=0.082
- http_req_failed: rate=0.000
- http_req_duration: p(99)=5.329, avg=4.707, min=1.658, med=4.855, max=5.339, p(90)=5.261, p(95)=5.291
- iterations: count=20.000, rate=4.861
- http_req_blocked: p(95)=0.021, p(99)=0.096, avg=0.016, min=0.004, med=0.011, max=0.115, p(90)=0.015
