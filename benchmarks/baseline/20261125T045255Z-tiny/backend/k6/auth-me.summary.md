# k6 summary

scenario: me

- iterations: count=48.000, rate=4.793
- http_req_duration: med=8.255, max=10.337, p(90)=9.612, p(95)=9.817, p(99)=10.121, avg=7.537, min=1.894
- http_req_receiving: med=0.118, max=0.230, p(90)=0.158, p(95)=0.183, p(99)=0.224, avg=0.108, min=0.024
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.127, p(90)=0.000, p(95)=0.000, p(99)=0.067
- vus: min=1.000, max=1.000
- http_req_blocked: p(95)=0.021, p(99)=0.107, avg=0.015, min=0.004, med=0.011, max=0.177, p(90)=0.016
- http_req_sending: p(90)=0.050, p(95)=0.059, p(99)=0.067, avg=0.042, min=0.012, med=0.041, max=0.069
- http_req_waiting: p(95)=9.656, p(99)=9.941, avg=7.387, min=1.829, med=8.075, max=10.160, p(90)=9.406
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(99)=10.121, avg=7.537, min=1.894, med=8.255, max=10.337, p(90)=9.612, p(95)=9.817
