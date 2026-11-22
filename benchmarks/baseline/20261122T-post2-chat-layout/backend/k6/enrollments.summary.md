# k6 summary

scenario: enrollments

- http_req_receiving: p(95)=0.344, p(99)=0.468, avg=0.141, min=0.011, med=0.121, max=0.522, p(90)=0.251
- iterations: count=245.000, rate=24.132
- http_req_blocked: med=0.011, max=0.223, p(90)=0.013, p(95)=0.024, p(99)=0.199, avg=0.015, min=0.002
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=5.000, max=5.000
- http_req_waiting: avg=5.281, min=0.778, med=4.225, max=52.514, p(90)=6.784, p(95)=6.995, p(99)=32.837
- http_req_sending: med=0.039, max=0.248, p(90)=0.052, p(95)=0.069, p(99)=0.141, avg=0.041, min=0.007
- http_req_duration{expected_response:true}: p(99)=32.950, avg=5.464, min=0.812, med=4.405, max=52.623, p(90)=7.051, p(95)=7.277
- http_req_failed: rate=0.000
- http_req_duration: p(95)=7.277, p(99)=32.950, avg=5.464, min=0.812, med=4.405, max=52.623, p(90)=7.051
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.150, avg=0.003, min=0.000, med=0.000, max=0.164
