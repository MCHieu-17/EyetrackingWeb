# k6 summary

scenario: enrollments

- http_req_failed: rate=0.000
- http_req_sending: min=0.005, med=0.039, max=0.109, p(90)=0.048, p(95)=0.058, p(99)=0.075, avg=0.038
- iterations: count=245.000, rate=24.129
- vus: min=5.000, max=5.000
- http_req_duration: avg=4.963, min=0.872, med=4.597, max=11.713, p(90)=7.085, p(95)=7.283, p(99)=8.888
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.106, avg=0.002, min=0.000, med=0.000, max=0.110
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: max=0.142, p(90)=0.013, p(95)=0.014, p(99)=0.140, avg=0.013, min=0.002, med=0.011
- http_req_receiving: med=0.114, max=0.671, p(90)=0.248, p(95)=0.316, p(99)=0.393, avg=0.131, min=0.008
- http_req_duration{expected_response:true}: avg=4.963, min=0.872, med=4.597, max=11.713, p(90)=7.085, p(95)=7.283, p(99)=8.888
- http_req_waiting: med=4.418, max=11.627, p(90)=6.821, p(95)=7.098, p(99)=8.718, avg=4.794, min=0.811
